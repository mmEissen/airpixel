from __future__ import annotations

import asyncio
import dataclasses
import enum
import socket
import time


class MonitoringError(Exception):
    pass


class PackageParsingError(MonitoringError):
    pass


class PackageSerializationError(MonitoringError):
    pass


class CommandParseError(MonitoringError):
    pass


class MonitorCommandError(MonitoringError):
    pass


class MonitorCommandVerb(str, enum.Enum):
    SUBSCRIBE = "sub"
    UNSUBSCRIBE = "unsub"
    CONNECT = "conn"


class MonitorCommandResponseType(bytes, enum.Enum):
    ERROR = b"err"
    SUCCESS = b"acc"


@dataclasses.dataclass
class MonitorCommandResponse:
    response: MonitorCommandResponseType
    info: str
    SEPERATOR = b":"

    def to_bytes(self) -> MonitorCommand:
        return self.response.value + self.SEPERATOR + bytes(info, "utf-8")


@dataclasses.dataclass
class MonitorCommand:
    verb: MonitorCommandVerb
    arg: str

    @classmethod
    def from_bytes(cls, data: bytes) -> MonitorCommand:
        try:
            verb_str, arg = str(data, "utf-8").split(" ")
        except ValueError as e:
            raise CommandParseError("Invalid command") from e
        try:
            verb = MonitorCommandVerb(verb)
        except ValueError:
            raise CommandParseError("Invalid command") from e
        return cls(verb, arg)


@dataclasses.dataclass
class MonitoringPackage:
    stream_id: str
    data: bytes

    STREAM_ID_SIZE = 128

    @classmethod
    def from_bytes(cls, raw_data: bytes) -> MonitoringPackage:
        if len(raw_data) < cls.STREAM_ID_SIZE:
            raise PackageParsingError("The package is invalid: Too short")
        header = raw_data[: cls.STREAM_ID_SIZE].lstrip(b"\x00")
        if not header:
            raise PackageParsingError("The package is invalid: No stream ID")
        return cls(str(header, "utf_8"), raw_data[cls.STREAM_ID_SIZE :])

    def to_bytes(self) -> bytes:
        if not self.stream_id:
            raise PackageSerializationError("stream_id can't be empty")
        stream_id_bytes = bytes(self.stream_id, "utf-8")
        if len(stream_id_bytes) > self.STREAM_ID_SIZE:
            raise PackageSerializationError("stream_id is too long")
        return (
            (self.STREAM_ID_SIZE - len(stream_id_bytes)) * b"\x00"
            + stream_id_bytes
            + self.data
        )


class MonitorDispachProtocol(asyncio.DatagramProtocol):
    def __init__(self, monitoring_server: MonitoringServer):
        super().__init__()
        self._monitoring_server = monitoring_server

    def datagram_received(self, data: bytes, addr: t.Tuple[str, int]) -> None:
        try:
            package = MonitoringPackage.from_bytes(data)
        except PackageParsingError:
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


class MonitorConnectionProtocol(asyncio.Protocol):
    PORT_SIZE = 2
    SEPPERATOR = b"\n"
    DEFAULT_RESPONSE = "acc"
    transport: asyncio.Transport

    def __init__(self, monitoring_server: MonitoringServer, keepalive_port: int):
        super().__init__()
        self._monitoring_server = monitoring_server
        self._current_package = b""
        self._keepalive_port = keepalive_port

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = t.cast(asyncio.Transport, transport)

    def _subscribe(self, arg: str) -> str:
        try:
            stream_id, port_str = arg.split(":")
        except ValueError:
            raise MonitorCommandError("expected 'stream_id:port'")
        try:
            port = int(port_str)
        except ValueError:
            raise MonitorCommandError("port should be a number")
        ip_address, _ = self.transport.get_extra_info("peername")
        self._monitoring_server.subscribe_to_stream((ip_address, port), stream_id)
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
            raise MonitorCommandError("port needs to be an int")
        ip_address, _ = self.transport.get_extra_info("peername")
        self._monitoring_server.connect(ip_address, udp_port)
        return str(self._keepalive_port)

    def execute_command(self, command: MonitorCommand) -> str:
        if command.verb == MonitorCommandVerb.SUBSCRIBE:
            return self._subscribe(command.arg)
        if command.verb == MonitorCommandVerb.UNSUBSCRIBE:
            return self._unsubscribe(command.arg)
        if command.verb == MonitorCommandVerb.CONNECT:
            return self._connect(command.arg)

    def respond_error(self, error: Exception) -> None:
        self.transport.write(
            MonitorCommandResponse(
                MonitorCommandResponseType.ERROR, str(e)
            )
        )
        self.transport.close()

    def respond_success(self, data: str) -> None:
        self.transport.write(
            MonitorCommandResponse(
                MonitorCommandResponseType.SUCCESS, bytes(data, "utf-8")
            )
        )
        self.transport.close()

    def data_received(self, data: bytes) -> None:
        *packages, self._current_package = (self._current_package + data).split(
            self.SEPPERATOR
        )
        if not packages:
            return
        try:
            command = MonitorCommand.from_bytes(data)
        except CommandParseError as e:
            self.respond_error(e)
            return
        try:
            response = self.execute_command(command)
        except MonitorCommandError as e:
            self.respond_error(e)
        else:
            self.respond_success(response)
