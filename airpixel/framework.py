import atexit
import asyncio
import collections
import dataclasses
import json
import logging
import socket
import subprocess
import time
import typing as t


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

BYTEORDER = "big"


def load_config(file_name):
    with open(file_name) as file_:
        return json.load(file_)


class KeepaliveProtocol(asyncio.DatagramProtocol):
    def __init__(self, process_registration):
        super().__init__()
        self._process_registration = process_registration

    def datagram_received(self, data, addr):
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
    def __init__(self, monitoring_server):
        super().__init__()
        self._monitoring_server = monitoring_server

    def datagram_received(self, data, addr):
        ip_address, _ = addr


class MonitorKeepaliveProtocol(asyncio.DatagramProtocol):
    def __init__(self, monitoring_server):
        super().__init__()
        self._monitoring_server = monitoring_server

    def datagram_received(self, data, addr):
        pass


_K = t.TypeVar("_K")
_KL = t.TypeVar("_KL")
_KR = t.TypeVar("_KR")
_V = t.TypeVar("_V")


class DoubleKeyedMapping(t.Generic[_KL, _KR, _V]):
    @dataclasses.dataclass
    class _Spec(t.Generic[_K]):
        indexes: t.Set[int] = dataclasses.field(default_factory=set)
        assoc_keys: t.Set[_K] = dataclasses.field(default_factory=set)

    def __init__(self):
        self._values: t.Dict[int, _V] = {}
        self._left_map: t.DefaultDict[
            _KL, DoubleKeyedMapping._Spec[_KR]
        ] = collections.defaultdict(self._Spec)
        self._right_map: t.DefaultDict[
            _KR, DoubleKeyedMapping.Spec[_KL]
        ] = collections.defaultdict(self._Spec)
        self._counter = 0

    def _get_indexed(self, indexes: t.Set[int]) -> t.List[_V]:
        return [self._values[i] for i in indexes]

    def _left_indexes(self, key: _KL) -> t.Set[int]:
        return self._left_map.get(key, self._Spec()).indexes

    def _right_indexes(self, key: _KR) -> t.Set[int]:
        return self._right_map.get(key, self._Spec()).indexes

    def get_left(self, key: _KL) -> t.List[_V]:
        return self._get_indexed(self._left_indexes(key))

    def get_right(self, key: _KR) -> t.List[_V]:
        return self._get_indexed(self._right_indexes(key))

    def _get_index(self, left_key: _KL, right_key: _KR) -> int:
        indexes = self._left_indexes(left_key) & self._right_indexes(right_key)
        if not indexes:
            raise KeyError
        return indexes.pop()

    def get(self, left_key: _KL, right_key: _KR) -> _V:
        return self._values[self._get_index(left_key, right_key)]

    def put(self, left_key: _KL, right_key: _KR, value: _V) -> None:
        try:
            index = self._get_index(left_key, right_key)
        except KeyError:
            pass
        else:
            self._values[index] = value
            return
        self._values[self._counter] = value
        self._left_map[left_key].indexes.add(self._counter)
        self._left_map[left_key].assoc_keys.add(right_key)
        self._right_map[right_key].indexes.add(self._counter)
        self._right_map[right_key].assoc_keys.add(left_key)
        self._counter += 1

    def delete_left(self, key: _KL) -> None:
        if key not in self._left_map:
            raise KeyError
        spec = self._left_map.get(key, self._Spec())
        for assoc_key in spec.assoc_keys:
            r_spec = self._right_map[assoc_key]
            r_spec.assoc_keys.remove(key)
            r_spec.indexes -= spec.indexes
            if not r_spec.assoc_keys:
                del self._right_map[assoc_key]
        for index in spec.indexes:
            del self._values[index]
        del self._left_map[key]

    def delete_right(self, key: _KR) -> None:
        if key not in self._right_map:
            raise KeyError
        spec = self._right_map.get(key, self._Spec())
        for assoc_key in spec.assoc_keys:
            l_spec = self._left_map[assoc_key]
            l_spec.assoc_keys.remove(key)
            l_spec.indexes -= spec.indexes
            if not l_spec.assoc_keys:
                del self._left_map[assoc_key]
        for index in spec.indexes:
            del self._values[index]
        del self._right_map[key]

    def delete(self, left_key: _KL, right_key: _KR) -> None:
        index = self._get_index(left_key, right_key)
        del self._values[index]
        left_spec = self._left_map[left_key]
        left_spec.assoc_keys.remove(right_key)
        left_spec.indexes.remove(index)
        right_spec = self._right_map[right_key]
        right_spec.assoc_keys.remove(left_key)
        right_spec.indexes.remove(index)


class MonitoringServer:
    def __init__(self, subscription_timeout: int = 3):
        self.subscription_timeout = subscription_timeout
        self._subscriptions: DoubleKeyedMapping[
            str, str, t.Tuple[str, int]
        ] = DoubleKeyedMapping()
        self._last_messages: t.Dict[str, float] = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(0)

    def dispatch_to_monitors(self, stream_id: str, data: bytes) -> None:
        monitor_addresses = self._subscriptions.get_right(stream_id)
        for address in monitor_addresses:
            try:
                self.socket.sendto(data, address)
            except OSError:
                pass

    def subscribe_to_stream(
        self, target_address: t.Tuple[str, int], stream_id: str
    ) -> None:
        ip_address, _ = target_address
        self._subscriptions.put(ip_address, stream_id, target_address)
        self._last_messages[ip_address] = time.time()

    def unsubscribe_from_stream(
        self, target_address: t.Tuple[str, int], stream_id: str
    ) -> None:
        ip_address, _ = target_address
        self._subscriptions.delete(ip_address, stream_id)

    def message_from(self, ip_address: str) -> None:
        self._last_messages[ip_address] = time.time()

    def purge_subscriptions(self) -> None:
        now = time.time()
        for ip_address, last_message in self._last_messages.items():
            if now - last_message > self.subscription_timeout:
                self._subscriptions.delete_left(ip_address)

    async def purge_forever(self) -> None:
        while True:
            self.purge_subscriptions()
            await asyncio.sleep(self.subscription_timeout / 4)


def _subprocess_factory(command):
    return subprocess.Popen("exec " + command, text=True, shell=True)


@dataclasses.dataclass
class ProcessMeta:
    process: t.Any
    ip_address: str
    device_id: str
    last_response: float


class ProcessRegistration:
    def __init__(self, config, subprocess_factory=_subprocess_factory, timeout=3):
        self._config = config
        self._subprocess_factory = subprocess_factory
        self._timeout = timeout
        self._processes = {}
        atexit.register(self.cleanup)

    def _kill_process(self, ip_address):
        if ip_address not in self._processes:
            return
        self._processes[ip_address].process.kill()
        self._processes[ip_address].process.communicate()
        del self._processes[ip_address]

    def response_from(self, ip_address):
        try:
            self._processes[ip_address].last_response = time.time()
        except KeyError:
            pass

    def purge_processes(self):
        now = time.time()
        dead_processes = {
            ip
            for ip, process in self._processes.items()
            if now - process.last_response >= self._timeout
        }
        for ip_address in dead_processes:
            log.info("Killing process for %s.", ip_address)
            self._kill_process(ip_address)

    async def purge_forever(self):
        while True:
            self.purge_processes()
            await asyncio.sleep(self._timeout / 4)

    def launch_for(self, device_id, ip_address, streaming_port):
        try:
            base_command = self._config[device_id]
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

    def cleanup(self):
        for process_meta in self._processes.values():
            process_meta.process.kill()


class ConnectionProtocol(asyncio.Protocol):
    PORT_SIZE = 2
    SEPPERATOR = b"\n"

    def __init__(self, process_registration, response_port):
        super().__init__()
        self._process_registration = process_registration
        self.transport = None
        self._current_package = b""
        self.response_port = response_port

    def connection_made(self, transport):
        log.info("New connection")
        self.transport = transport

    def _register_device(self, registration_bytes):
        port = int.from_bytes(registration_bytes[: self.PORT_SIZE], BYTEORDER)
        device_id = str(registration_bytes[self.PORT_SIZE :], "utf-8")
        ip_address, _ = self.transport.get_extra_info("peername")
        self._process_registration.launch_for(device_id, ip_address, port)
        self.transport.write(
            int.to_bytes(self.response_port, self.PORT_SIZE, BYTEORDER)
        )

    def data_received(self, data):
        *packages, self._current_package = (self._current_package + data).split(
            self.SEPPERATOR
        )
        if not packages:
            return
        log.info("Received %r", packages)
        self._register_device(packages[0])
        self.transport.close()


async def main():
    config = load_config("airpixel.json")

    log.info(config)

    loop = asyncio.get_running_loop()
    process_registration = ProcessRegistration(config["devices"])
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: KeepaliveProtocol(process_registration),
        local_addr=(config["address"], config["udp_port"]),
        family=socket.AF_INET,
    )

    server = await loop.create_server(
        lambda: ConnectionProtocol(process_registration, config["udp_port"]),
        config["address"],
        config["port"],
    )

    async with server:
        await asyncio.gather(
            server.serve_forever(), process_registration.purge_forever()
        )


if __name__ == "__main__":
    asyncio.run(main())
