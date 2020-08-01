from __future__ import annotations

import asyncio
import dataclasses
import enum
import socket
import time
import typing as t


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


class CommandVerb(str, enum.Enum):
    SUBSCRIBE = "sub"
    UNSUBSCRIBE = "unsub"
    CONNECT = "conn"


class CommandResponseType(bytes, enum.Enum):
    ERROR = b"err"
    SUCCESS = b"acc"


@dataclasses.dataclass
class CommandResponse:
    response: CommandResponseType
    info: str
    SEPERATOR = b":"

    def to_bytes(self) -> Command:
        return self.response.value + self.SEPERATOR + bytes(self.info, "utf-8")


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
        return cls(verb, arg)


@dataclasses.dataclass
class Package:
    stream_id: str
    data: bytes

    STREAM_ID_SIZE = 128

    @classmethod
    def from_bytes(cls, raw_data: bytes) -> Package:
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


class DispachProtocol(asyncio.DatagramProtocol):
    def __init__(self, monitoring_server: Server):
        super().__init__()
        self._monitoring_server = monitoring_server

    def datagram_received(self, data: bytes, addr: t.Tuple[str, int]) -> None:
        try:
            package = Package.from_bytes(data)
        except PackageParsingError:
            return
        self._monitoring_server.dispatch_to_monitors(package.stream_id, package.data)


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
        stream = self._streams.setdefault(stream_id, Stream(stream_id))
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
        self.transport.write(CommandResponse(CommandResponseType.ERROR, str(error)))
        self.transport.close()

    def respond_success(self, data: str) -> None:
        self.transport.write(CommandResponse(CommandResponseType.SUCCESS, data))
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
