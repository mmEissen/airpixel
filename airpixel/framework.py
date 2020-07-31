from __future__ import annotations

import atexit
import asyncio
import collections
import dataclasses
import logging
import socket
import subprocess
import time
import typing as t

import yaml

from airpixel import monitoring


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

BYTEORDER = "big"


class KeepaliveProtocol(asyncio.DatagramProtocol):
    def __init__(self, process_registration: ProcessRegistration):
        super().__init__()
        self._process_registration = process_registration

    def datagram_received(self, data: bytes, addr: t.Tuple[str, int]) -> None:
        ip_address, _ = addr
        frames, rendered = (int(n) for n in str(data, "utf-8").split())
        if frames:
            log.info(
                "%s: Received: %s Shown: %s Ratio: %s",
                ip_address,
                frames,
                rendered,
                rendered / frames,
            )
        self._process_registration.response_from(ip_address)


class MonitorDispachProtocol(asyncio.DatagramProtocol):
    def __init__(self, monitoring_server: MonitoringServer):
        super().__init__()
        self._monitoring_server = monitoring_server

    def datagram_received(self, data: bytes, addr: t.Tuple[str, int]) -> None:
        try:
            package = monitoring.MonitoringPackage.from_bytes(data)
        except monitoring.PackageParsingError:
            log.warning("Received invalid monitoring package!", extra={"package": data})
            return
        self._monitoring_server.dispatch_to_monitors(package.stream_id, package.data)


class MonitorKeepaliveProtocol(asyncio.DatagramProtocol):
    def __init__(self, monitoring_server: MonitoringServer):
        super().__init__()
        self._monitoring_server = monitoring_server

    def datagram_received(self, data: bytes, addr: t.Tuple[str, int]) -> None:
        ip_address, _ = addr
        self._monitoring_server.message_from(ip_address)


@dataclasses.dataclass
class MonitorDevice:
    ip_address: str
    udp_port: int
    last_message: float = 0
    subscriptions: t.Dict[str, MonitorStream] = dataclasses.field(default_factory=dict)

    def subscribe_to(self, stream: MonitorStream) -> None:
        self.subscriptions[stream.stream_id] = stream
        stream.add_subscriber(self)

    def unsubscribe_from(self, stream: MonitorStream) -> None:
        try:
            subscription = self.subscriptions.pop(stream.stream_id)
        except KeyError:
            return
        subscription.remove_subscriber(self)

    def unsubscribe_all(self) -> t.List[MonitorStream]:
        for subscription in self.subscriptions.values():
            subscription.remove_subscriber(self)
        old_subscriptions = [
            subscription for subscription in self.subscriptions.values()
        ]
        self.subscriptions = {}
        return old_subscriptions

    def address(self) -> t.Tuple[str, int]:
        return (self.ip_address, self.udp_port)

    def heartbeat(self) -> None:
        self.last_message = time.time()


@dataclasses.dataclass
class MonitorStream:
    stream_id: str
    subscribers: t.Dict[str, MonitorDevice] = dataclasses.field(default_factory=dict)

    def add_subscriber(self, monitor: MonitorDevice) -> None:
        self.subscribers[monitor.ip_address] = monitor

    def remove_subscriber(self, monitor: MonitorDevice) -> None:
        del self.subscribers[monitor.ip_address]

    def has_subscribers(self) -> bool:
        return bool(self.subscribers)


class MonitoringServer:
    def __init__(self, subscription_timeout: int = 3):
        self.subscription_timeout = subscription_timeout
        self._devices: t.Dict[str, MonitorDevice] = {}
        self._streams: t.Dict[str, MonitorStream] = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(0)

    def connect(self, ip_address: str, port: int) -> None:
        device = self._devices.setdefault(ip_address, MonitorDevice(ip_address, port))
        device.heartbeat()

    def dispatch_to_monitors(self, stream_id: str, data: bytes) -> None:
        try:
            stream = self._streams[stream_id]
        except KeyError:
            return
        for subscriber in stream.subscribers.values():
            try:
                self.socket.sendto(data, subscriber.address())
            except OSError:
                pass

    def subscribe_to_stream(self, ip_address: str, stream_id: str) -> None:
        try:
            device = self._devices[ip_address]
        except KeyError:
            return
        stream = self._streams.setdefault(stream_id, MonitorStream(stream_id))
        device.subscribe_to(stream)

    def unsubscribe_from_stream(self, ip_address: str, stream_id: str) -> None:
        try:
            device = self._devices[ip_address]
            stream = self._streams[stream_id]
        except KeyError:
            return
        del self._devices[ip_address]
        device.unsubscribe_from(stream)
        self._clean_stream(stream)

    def _clean_stream(self, stream: MonitorStream) -> None:
        if not stream.has_subscribers():
            del self._streams[stream.stream_id]

    def message_from(self, ip_address: str) -> None:
        try:
            device = self._devices[ip_address]
        except KeyError:
            return
        device.heartbeat()

    def purge_subscriptions(self) -> None:
        now = time.time()
        to_kill: t.Set[str] = set()
        for device in self._devices.values():
            if now - device.last_message < self.subscription_timeout:
                continue
            to_kill.add(device.ip_address)
            streams = device.unsubscribe_all()
            for stream in streams:
                self._clean_stream(stream)
        for ip_address in to_kill:
            del self._devices[ip_address]

    async def purge_forever(self) -> None:
        while True:
            self.purge_subscriptions()
            await asyncio.sleep(self.subscription_timeout / 4)


def _subprocess_factory(command: str) -> subprocess.Popen:
    return subprocess.Popen("exec " + command, text=True, shell=True)


@dataclasses.dataclass
class ProcessMeta:
    process: subprocess.Popen
    ip_address: str
    device_id: str
    last_response: float


class ProcessRegistration:
    def __init__(
        self,
        device_configs: t.Iterable[DeviceConfig],
        subprocess_factory: t.Callable[[str], subprocess.Popen] = _subprocess_factory,
        timeout: float = 3,
    ):
        self._commands = {
            device_config.device_id: device_config.command_template
            for device_config in device_configs
        }
        self._subprocess_factory = subprocess_factory
        self._timeout = timeout
        self._processes: t.Dict[str, ProcessMeta] = {}
        atexit.register(self.cleanup)

    def _kill_process(self, ip_address: str) -> None:
        if ip_address not in self._processes:
            return
        self._processes[ip_address].process.kill()
        self._processes[ip_address].process.communicate()
        del self._processes[ip_address]

    def response_from(self, ip_address: str) -> None:
        try:
            self._processes[ip_address].last_response = time.time()
        except KeyError:
            pass

    def purge_processes(self) -> None:
        now = time.time()
        dead_processes = {
            ip
            for ip, process in self._processes.items()
            if now - process.last_response >= self._timeout
        }
        for ip_address in dead_processes:
            log.info("Killing process for %s.", ip_address)
            self._kill_process(ip_address)

    async def purge_forever(self) -> None:
        while True:
            self.purge_processes()
            await asyncio.sleep(self._timeout / 4)

    def launch_for(self, device_id: str, ip_address: str, streaming_port: int) -> None:
        try:
            base_command = self._commands[device_id]
        except KeyError:
            log.warning("No process configured for device ID %s", device_id)
            return
        try:
            base_command = base_command.format(
                ip_address=ip_address, port=str(streaming_port)
            )
        except KeyError:
            log.warning(
                "Invalid format string for subprocess command for device %s", device_id
            )
            return
        log.info("Launching process for device %s: `%s`", device_id, base_command)
        self._kill_process(ip_address)
        self._processes[ip_address] = ProcessMeta(
            self._subprocess_factory(base_command), ip_address, device_id, time.time()
        )

    def cleanup(self) -> None:
        for process_meta in self._processes.values():
            process_meta.process.kill()


class ConnectionProtocol(asyncio.Protocol):
    PORT_SIZE = 2
    SEPPERATOR = b"\n"
    transport: asyncio.Transport

    def __init__(self, process_registration: ProcessRegistration, response_port: int):
        super().__init__()
        self._process_registration = process_registration
        self._current_package = b""
        self.response_port = response_port

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        log.info("New connection")
        self.transport = t.cast(asyncio.Transport, transport)

    def _register_device(self, registration_bytes: bytes) -> None:
        port = int.from_bytes(registration_bytes[: self.PORT_SIZE], BYTEORDER)
        device_id = str(registration_bytes[self.PORT_SIZE :], "utf-8")
        ip_address, _ = self.transport.get_extra_info("peername")
        self._process_registration.launch_for(device_id, ip_address, port)
        self.transport.write(
            int.to_bytes(self.response_port, self.PORT_SIZE, BYTEORDER)
        )

    def data_received(self, data: bytes) -> None:
        *packages, self._current_package = (self._current_package + data).split(
            self.SEPPERATOR
        )
        if not packages:
            return
        log.info("Received %r", packages)
        self._register_device(packages[0])
        self.transport.close()


@dataclasses.dataclass
class Config:
    address: str
    port: int
    udp_port: int
    devices: t.List[DeviceConfig]

    @classmethod
    def from_dict(cls, dict_: t.Dict[str, t.Any]) -> Config:
        return cls(
            dict_["address"],
            dict_["port"],
            dict_["udp_port"],
            [DeviceConfig.from_dict(d) for d in dict_["devices"]],
        )

    @classmethod
    def load(cls, file_name: str) -> Config:
        with open(file_name) as file_:
            return cls.from_dict(yaml.load(file_))


@dataclasses.dataclass
class DeviceConfig:
    device_id: str
    command_template: str

    @classmethod
    def from_dict(cls, dict_: t.Dict[str, t.Any]) -> DeviceConfig:
        return cls(dict_["device_id"], dict_["command_template"],)


class Application:
    def __init__(self, config: Config):
        self.config = config
        self.process_registration = ProcessRegistration(config.devices)

    async def run_forever(self) -> None:
        loop = asyncio.get_running_loop()

        await loop.create_datagram_endpoint(
            lambda: KeepaliveProtocol(self.process_registration),
            local_addr=(self.config.address, self.config.udp_port),
            family=socket.AF_INET,
        )

        server = await loop.create_server(
            lambda: ConnectionProtocol(self.process_registration, self.config.udp_port),
            self.config.address,
            self.config.port,
        )

        async with server:
            await asyncio.gather(
                server.serve_forever(), self.process_registration.purge_forever()
            )


def main() -> None:
    config = Config.load("airpixel.yaml")

    log.info(config)

    app = Application(config)
    try:
        asyncio.run(app.run_forever())
    except KeyboardInterrupt:
        log.info("Application shut down by user (keyboard interrupt)")


if __name__ == "__main__":
    main()
