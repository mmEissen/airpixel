from __future__ import annotations

import dataclasses
import enum


class MonitoringError(Exception):
    pass


class PackageParsingError(MonitoringError):
    pass


class PackageSerializationError(MonitoringError):
    pass


class CommandParseError(MonitoringError):
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
