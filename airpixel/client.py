import abc
import socket
import typing as t
import threading
import time

import numpy as np

from . import gamma_table


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


class LoopingThread(threading.Thread, abc.ABC):
    def __init__(self, *args: t.Any, **kwargs: t.Any):
        super().__init__(*args, daemon=True, **kwargs)
        self._is_running = False

    @abc.abstractmethod
    def loop(self) -> None:
        pass

    def setup(self) -> None:
        self._is_running = True

    def tear_down(self) -> None:
        pass

    def run(self) -> None:
        self.setup()
        while self._is_running:
            self.loop()
        self.tear_down()

    def stop(self) -> None:
        self._is_running = False


class AirClient:
    def __init__(
        self, remote_ip=str, remote_port=int, color_method: ColorMethod = ColorMethodGRB
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

    def show_frame(self, frame: t.List[Pixel]) -> None:
        raw_pixels = np.concatenate(
            [self.color_method.to_bytes(pixel) for pixel in frame]
        )
        raw_pixels = gamma_table.GAMMA_TABLE[(raw_pixels * 255).astype("uint8")]
        frame_number = self.frame_number.to_bytes(
            UDPConstants.FRAME_NUMBER_BYTES, byteorder=UDPConstants.ENCODING_BYTEORDER
        )
        self.send_bytes(frame_number + bytes(raw_pixels))
        self.frame_number += 1


class AutoClient(LoopingThread):
    SLEEP = 0.035

    def begin(
        self, remote_ip=str, remote_port=int, color_method: ColorMethod = ColorMethodGRB
    ) -> None:
        self._client = AirClient(remote_ip, remote_port, color_method)
        self._frame = [Pixel(0, 0, 0)]
        self._lock = threading.Lock()

        self.start()

    def show_frame(self, frame):
        with self._lock:
            self._frame = list(frame)

    def loop(self):
        with self._lock:
            self._client.show_frame(self._frame)
        time.sleep(self.SLEEP)
