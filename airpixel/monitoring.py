from __future__ import annotations

import asyncio
import dataclasses
import enum
import logging
import logging.config
import socket
import time
import typing as t

import yaml

from airpixel import logging_config

log = logging.getLogger(__name__)


class MonitoringError(Exception):
    pass


class PackageParsingError(MonitoringError):
    pass


class PackageSerializationError(MonitoringError):
    pass


class CommandParseError(MonitoringError):
    pass


class CommandError(MonitoringError):
    pass


class CommandResponseParseError(MonitoringError):
    pass


@enum.unique
class CommandVerb(str, enum.Enum):
    SUBSCRIBE = "sub"
    UNSUBSCRIBE = "unsub"
    CONNECT = "conn"


@enum.unique
class CommandResponseType(bytes, enum.Enum):
    ERROR = b"err"
    SUCCESS = b"acc"


@dataclasses.dataclass
class CommandResponse:
    response: CommandResponseType
    info: str
    SEPERATOR = b":"

    def to_bytes(self) -> bytes:
        return self.response.value + self.SEPERATOR + bytes(self.info, "utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> CommandResponse:
        try:
            response, info = data.split(cls.SEPERATOR)
        except ValueError as e:
            raise CommandResponseParseError("Invalid command response") from e
        try:
            response = CommandResponseType(response)
        except ValueError as e:
            raise CommandResponseParseError(
                f"Invalid command response: {str(response, 'utf-8')}"
            ) from e
        return cls(response, str(info, "utf-8"))


@dataclasses.dataclass
class Command:
    verb: CommandVerb
    arg: str

    @classmethod
    def from_bytes(cls, data: bytes) -> Command:
        try:
            verb_str, arg = str(data, "utf-8").split(" ")
        except ValueError as e:
            raise CommandParseError("Invalid command") from e
        try:
            verb = CommandVerb(verb_str)
        except ValueError as e:
            raise CommandParseError("Invalid command") from e
        return cls(verb, arg.strip())

    def to_bytes(self) -> bytes:
        return bytes(self.verb.value, "utf-8") + b" " + bytes(self.arg, "utf-8") + b"\n"


@dataclasses.dataclass
class Package:
    stream_id: str
    data: bytes

    SEPARATOR = b"\x00"

    @classmethod
    def from_bytes(cls, raw_data: bytes) -> Package:
        try:
            header, data = raw_data.split(cls.SEPARATOR, 1)
        except ValueError as e:
            raise PackageParsingError("Invalid package") from e
        if not header:
            raise PackageParsingError("The package is invalid: No stream ID")
        return cls(str(header, "utf-8"), data)

    def to_bytes(self) -> bytes:
        if not self.stream_id:
            raise PackageSerializationError("stream_id can't be empty")
        stream_id_bytes = bytes(self.stream_id, "utf-8")
        return stream_id_bytes + self.SEPARATOR + self.data


class DispachProtocol(asyncio.DatagramProtocol):
    def __init__(self, monitoring_server: Server):
        super().__init__()
        self._monitoring_server = monitoring_server

    def datagram_received(self, data: bytes, addr: t.Tuple[str, int]) -> None:
        try:
            package = Package.from_bytes(data)
        except PackageParsingError:
            log.debug("Invalid package", exc_info=True)
            return
        self._monitoring_server.dispatch_to_monitors(package.stream_id, data)


class KeepaliveProtocol(asyncio.DatagramProtocol):
    def __init__(self, monitoring_server: Server):
        super().__init__()
        self._monitoring_server = monitoring_server

    def datagram_received(self, data: bytes, addr: t.Tuple[str, int]) -> None:
        ip_address, _ = addr
        self._monitoring_server.message_from(ip_address)


@dataclasses.dataclass
class Device:
    ip_address: str
    udp_port: int
    last_message: float = 0
    subscriptions: t.Dict[str, Stream] = dataclasses.field(default_factory=dict)

    def subscribe_to(self, stream: Stream) -> None:
        self.subscriptions[stream.stream_id] = stream
        stream.add_subscriber(self)

    def unsubscribe_from(self, stream: Stream) -> None:
        try:
            subscription = self.subscriptions.pop(stream.stream_id)
        except KeyError:
            return
        subscription.remove_subscriber(self)

    def unsubscribe_all(self) -> t.List[Stream]:
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
class Stream:
    stream_id: str
    subscribers: t.Dict[str, Device] = dataclasses.field(default_factory=dict)

    def add_subscriber(self, monitor: Device) -> None:
        self.subscribers[monitor.ip_address] = monitor

    def remove_subscriber(self, monitor: Device) -> None:
        del self.subscribers[monitor.ip_address]

    def has_subscribers(self) -> bool:
        return bool(self.subscribers)


class Server:
    def __init__(self, subscription_timeout: int = 3):
        self.subscription_timeout = subscription_timeout
        self._devices: t.Dict[str, Device] = {}
        self._streams: t.Dict[str, Stream] = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(0)

    def connect(self, ip_address: str, port: int) -> None:
        device = self._devices.setdefault(ip_address, Device(ip_address, port))
        device.heartbeat()
        log.debug("Monitor %s connected", ip_address)

    def dispatch_to_monitors(self, stream_id: str, data: bytes) -> None:
        log.debug("dispatching for stream %s", stream_id)
        try:
            stream = self._streams[stream_id]
        except KeyError:
            log.debug("No subscriptions for %s", stream_id)
            return
        for subscriber in stream.subscribers.values():
            try:
                self.socket.sendto(data, subscriber.address())
            except OSError:
                pass
            log.debug("Sent data for '%s' to %s", stream_id, subscriber.ip_address)

    def subscribe_to_stream(self, ip_address: str, stream_id: str) -> None:
        try:
            device = self._devices[ip_address]
        except KeyError:
            return
        stream = self._streams.setdefault(stream_id, Stream(stream_id))
        device.subscribe_to(stream)
        log.debug("%s subscribed to stream %s", ip_address, stream_id)

    def unsubscribe_from_stream(self, ip_address: str, stream_id: str) -> None:
        try:
            device = self._devices[ip_address]
            stream = self._streams[stream_id]
        except KeyError:
            return
        del self._devices[ip_address]
        device.unsubscribe_from(stream)
        self._clean_stream(stream)

    def _clean_stream(self, stream: Stream) -> None:
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
            log.debug("Killed Monitor %s", ip_address)
            del self._devices[ip_address]

    async def purge_forever(self) -> None:
        while True:
            self.purge_subscriptions()
            await asyncio.sleep(self.subscription_timeout / 4)


class ConnectionProtocol(asyncio.Protocol):
    PORT_SIZE = 2
    SEPPERATOR = b"\n"
    DEFAULT_RESPONSE = "acc"
    transport: asyncio.Transport

    def __init__(self, monitoring_server: Server, keepalive_port: int):
        super().__init__()
        self._monitoring_server = monitoring_server
        self._current_package = b""
        self._keepalive_port = keepalive_port

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = t.cast(asyncio.Transport, transport)

    def _subscribe(self, arg: str) -> str:
        stream_id = arg
        ip_address, _ = self.transport.get_extra_info("peername")
        self._monitoring_server.subscribe_to_stream(ip_address, stream_id)
        return self.DEFAULT_RESPONSE

    def _unsubscribe(self, arg: str) -> str:
        stream_id = arg
        ip_address, _ = self.transport.get_extra_info("peername")
        self._monitoring_server.unsubscribe_from_stream(ip_address, stream_id)
        return self.DEFAULT_RESPONSE

    def _connect(self, args: str) -> str:
        try:
            udp_port = int(args)
        except ValueError:
            raise CommandError("port needs to be an int")
        ip_address, _ = self.transport.get_extra_info("peername")
        self._monitoring_server.connect(ip_address, udp_port)
        return str(self._keepalive_port)

    def execute_command(self, command: Command) -> str:
        if command.verb == CommandVerb.SUBSCRIBE:
            return self._subscribe(command.arg)
        if command.verb == CommandVerb.UNSUBSCRIBE:
            return self._unsubscribe(command.arg)
        if command.verb == CommandVerb.CONNECT:
            return self._connect(command.arg)
        raise CommandError("unrecognized command verb")

    def respond_error(self, error: Exception) -> None:
        self.transport.write(
            CommandResponse(CommandResponseType.ERROR, str(error)).to_bytes()
        )
        self.transport.close()

    def respond_success(self, data: str) -> None:
        self.transport.write(
            CommandResponse(CommandResponseType.SUCCESS, data).to_bytes()
        )
        self.transport.close()

    def data_received(self, data: bytes) -> None:
        *packages, self._current_package = (self._current_package + data).split(
            self.SEPPERATOR
        )
        if not packages:
            return
        try:
            command = Command.from_bytes(data)
        except CommandParseError as e:
            self.respond_error(e)
            return
        try:
            response = self.execute_command(command)
        except CommandError as e:
            self.respond_error(e)
        else:
            self.respond_success(response)


@dataclasses.dataclass
class Config:
    address: str
    port: int
    unix_socket: str

    @classmethod
    def from_dict(cls, dict_: t.Dict[str, t.Any]) -> Config:
        return cls(
            dict_["address"],
            dict_["port"],
            dict_["unix_socket"],
        )

    @classmethod
    def load(cls, file_name: str) -> Config:
        with open(file_name) as file_:
            return cls.from_dict(yaml.safe_load(file_)["monitoring"])


class Application:
    def __init__(self, config: Config):
        self.config = config
        self.monitoring_server = Server()

    async def run_forever(self) -> None:
        loop = asyncio.get_running_loop()

        transport, _ = await loop.create_datagram_endpoint(
            lambda: KeepaliveProtocol(self.monitoring_server),
            local_addr=(self.config.address, 0),
            family=socket.AF_INET,
        )
        _, keepalive_port = transport.get_extra_info("sockname")

        log.info(
            "Monitoring keepalive endpoint up on %(keepalive_port)s",
            {"keepalive_port": keepalive_port},
        )

        await loop.create_datagram_endpoint(
            lambda: DispachProtocol(self.monitoring_server),
            local_addr=t.cast(t.Any, self.config.unix_socket),
            family=socket.AF_UNIX,
        )

        log.info(
            "Monitoring dispatch endpoint up on %(unix_socket)s",
            {"unix_socket": self.config.unix_socket},
        )

        server = await loop.create_server(
            lambda: ConnectionProtocol(self.monitoring_server, keepalive_port),
            self.config.address,
            self.config.port,
        )

        log.info(
            "Monitoring server created on %(address)s:%(port)s",
            {"address": self.config.address, "port": self.config.port},
        )

        async with server:
            await asyncio.gather(
                server.serve_forever(), self.monitoring_server.purge_forever()
            )


def main() -> None:
    logging_config.load("airpixel.yaml")
    config = Config.load("airpixel.yaml")

    log.info("Monitoring configuration loaded")

    app = Application(config)
    try:
        asyncio.run(app.run_forever())
    except KeyboardInterrupt:
        log.info("Application shut down by user (keyboard interrupt)")


if __name__ == "__main__":
    main()
