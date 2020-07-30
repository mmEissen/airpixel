import typing as t
import dataclasses


class MonitoringError(Exception):
    pass


class PackageParsingError(MonitoringError):
    pass


class PackageSerializationError(MonitoringError):
    pass


@dataclasses.dataclass
class MonitoringPackage:
    stream_id: str
    data: bytes

    STREAM_ID_SIZE = 128

    @classmethod
    def from_bytes(cls, raw_data: bytes):
        if len(raw_data) < cls.STREAM_ID_SIZE:
            raise PackageParsingError("The package is invalid: Too short")
        header = raw_data[:cls.STREAM_ID_SIZE].lstrip(b"\x00")
        if not header:
            raise PackageParsingError("The package is invalid: No stream ID")
        return cls(str(header, "utf_8"), raw_data[cls.STREAM_ID_SIZE:])


    def to_bytes(self):
        if not self.stream_id:
            raise PackageSerializationError("stream_id can't be empty")
        stream_id_bytes = bytes(self.stream_id, "utf-8")
        if len(stream_id_bytes) > self.STREAM_ID_SIZE:
            raise PackageSerializationError("stream_id is too long")
        return (self.STREAM_ID_SIZE - len(stream_id_bytes)) * b"\x00" + stream_id_bytes + self.data
