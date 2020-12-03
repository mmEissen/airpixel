import abc
import io
import socket
import typing as t

import numpy as np  # type: ignore

from airpixel import gamma_table, monitoring


class UDPConstants:
    ENCODING_BYTEORDER = "big"
    FRAME_NUMBER_BYTES = 8
    BITS_IN_BYTE = 8
    MAX_PACKET_SIZE = 65507


class ColorMethod:
    @staticmethod
    @abc.abstractmethod
    def to_bytes(pixel: "Pixel") -> np.ndarray:
        pass


class ColorMethodRGB(ColorMethod):
    @staticmethod
    @abc.abstractmethod
    def to_bytes(pixel: "Pixel") -> np.ndarray:
        return pixel.values


class ColorMethodRGBW(ColorMethod):
    # For now just r, g, b, 0.
    # This might have a better solution:
    # http://www.mirlab.org/conference_papers/International_Conference/ICASSP%202014/papers/p1214-lee.pdf
    @staticmethod
    @abc.abstractmethod
    def to_bytes(pixel: "Pixel") -> np.ndarray:
        return np.append(pixel.values, [0])


class ColorMethodGRB(ColorMethod):
    @staticmethod
    @abc.abstractmethod
    def to_bytes(pixel: "Pixel") -> np.ndarray:
        red, green, blue = pixel.values
        return np.array((green, red, blue))


class ColorMethodGRBW(ColorMethod):
    @staticmethod
    @abc.abstractmethod
    def to_bytes(pixel: "Pixel") -> np.ndarray:
        red, green, blue, white = ColorMethodRGBW.to_bytes(pixel)
        return np.array((green, red, blue, white))


class Pixel:
    def __init__(self, red: float, green: float, blue: float) -> None:
        self.values = np.array((red, green, blue))

    def __repr__(self) -> str:
        return "P{:.2}|{:.2}|{:.2}".format(
            float(self.values[0]), float(self.values[1]), float(self.values[2])
        )


class AirClient:
    def __init__(
        self,
        remote_ip: str,
        remote_port: int,
        color_method: t.Type[ColorMethod] = ColorMethodGRB,
    ) -> None:
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(0)
        self.frame_number = 0
        self.color_method = color_method

    def send_bytes(self, message: bytes) -> None:
        try:
            self.socket.sendto(message, (self.remote_ip, self.remote_port))
        except OSError:
            pass
    
    def _frame_number_bytes(self) -> bytes:
        return self.frame_number.to_bytes(
            UDPConstants.FRAME_NUMBER_BYTES, byteorder=UDPConstants.ENCODING_BYTEORDER
        )

    def show_bytes(self, message: bytes) -> None:
        self.send_bytes(self._frame_number_bytes() + message)
        self.frame_number += 1

    def show_frame(self, frame: t.List[Pixel]) -> None:
        raw_pixels = np.concatenate(
            [self.color_method.to_bytes(pixel) for pixel in frame]
        )
        raw_pixels = gamma_table.GAMMA_TABLE[(raw_pixels * 255).astype("uint8")]
        self.show_bytes(bytes(raw_pixels))


class MonitorClient:
    def __init__(self, socket_address: str):
        self.socket_address = socket_address
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.socket.settimeout(0)

    def send_bytes(self, message: bytes) -> None:
        try:
            self.socket.sendto(message, self.socket_address)
        except OSError:
            pass

    def send_data(self, stream_id: str, data: bytes) -> None:
        bytes_ = monitoring.Package(stream_id, data).to_bytes()
        self.send_bytes(bytes_)

    def send_np_array(self, stream_id: str, data: np.array) -> None:
        file_ = io.BytesIO()
        np.save(file_, data, False)
        self.send_data(stream_id, file_.getvalue())
