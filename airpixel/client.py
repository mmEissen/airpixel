import abc
import socket
import time
import threading
import typing as t

import numpy as np

from . import gamma_table


class AirClientConnectionError(OSError):
    pass


class NotConnectedError(Exception):
    pass


class PixelOutOfRangeError(IndexError):
    pass


class Pixel:
    def __init__(self, red, green, blue) -> None:
        self._values = np.array((red, green, blue))

    def __repr__(self) -> str:
        red, green, blue = (int(c) for c in self.get_rgb() * 255)
        return f"<{self.__class__.__name__}:{red:0>3},{green:0>3},{blue:0>3}>"

    def get_rgbw(self):
        # For now just r, g, b, 0.
        # This might have a better solution:
        # http://www.mirlab.org/conference_papers/International_Conference/ICASSP%202014/papers/p1214-lee.pdf
        return np.append(self._values, [0])

    def get_rgb(self):
        return self._values


class AirDetective:
    def __init__(self, port: int) -> None:
        self._socket = None
        self._port = port

    def _bind_socket(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except OSError as error:
            self._socket = None
            raise AirClientConnectionError("Error creating socket") from error
        try:
            self._socket.bind(("", self._port))
        except OSError as error:
            self._socket.close()
            self._socket = None
            raise AirClientConnectionError("Error while binding the socket") from error

    def _find_ip(self):
        message = b""
        while message != b"LEDRing\n":
            message, _, _, (ip_address, _) = self._socket.recvmsg(32)
        return ip_address

    def find_ring_ip(self):
        self._bind_socket()
        return self._find_ip()


class AbstractClient(abc.ABC):
    num_colors = 4

    def __init__(self, num_leds: int) -> None:
        self.num_leds = num_leds
        self.frame_size = num_leds * self.num_colors
        self._pixels = self.clear_frame()

    def __repr__(self) -> str:
        return "{}<{}X{}>".format(
            self.__class__.__name__, self.num_colors, self.num_leds
        )

    def set_frame(self, frame: t.List[Pixel]) -> None:
        self._pixels = frame

    def clear_frame(self) -> t.List[Pixel]:
        return [Pixel(0, 0, 0) for _ in range(self.num_leds)]

    @abc.abstractmethod
    def connect(self) -> None:
        pass

    @abc.abstractmethod
    def disconnect(self) -> None:
        pass

    @abc.abstractmethod
    def show(self) -> None:
        pass

    @abc.abstractmethod
    def is_connected(self) -> bool:
        pass


class AirClient(AbstractClient):
    _frame_number_bytes = 4

    def __init__(self, port: int, num_leds: int) -> None:
        super().__init__(num_leds)
        self._port = port
        self._ring_address = None
        self._tcp_socket: t.Optional[socket.socket] = None
        self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def is_connected(self) -> bool:
        return self._tcp_socket is not None

    def connect(self) -> None:
        self._ring_address = AirDetective(self._port).find_ring_ip()
        try:
            self._tcp_socket = socket.socket()
        except OSError as error:
            self._tcp_socket = None
            raise AirClientConnectionError("Error creating socket") from error
        try:
            self._tcp_socket.connect((self._ring_address, self._port))
        except OSError as error:
            self._tcp_socket.close()
            self._tcp_socket = None
            raise AirClientConnectionError("Error connecting to server") from error

    def disconnect(self) -> None:
        if self.is_connected():
            self._tcp_socket = t.cast(socket.socket, self._tcp_socket)
            self._tcp_socket.close()

    def _pixel_list(self):
        return [pixel.get_rgbw() for pixel in self._pixels]

    def _raw_data(self):
        pixels = np.concatenate(self._pixel_list())
        pixels = gamma_table.GAMMA_TABLE[(pixels * 255).astype("uint8")]
        return bytes(self._frame_number_bytes) + bytes(pixels)

    def show(self) -> None:
        if not self.is_connected():
            raise NotConnectedError("Client must be connected before calling show()!")
        self._udp_socket.sendto(self._raw_data(), (self._ring_address, self._port))


class RenderLoop(threading.Thread):
    def __init__(self, air_client, update_fnc, max_framerate=120):
        super().__init__(name="render-loop-thread")
        self._frame_period = 1 / max_framerate
        self._update_fnc = update_fnc
        self._is_running = False
        self._air_client = air_client

    def _loop(self):
        draw_start_time = time.time()
        new_frame = self._update_fnc(draw_start_time)
        self._air_client.set_frame(new_frame)
        self._air_client.show()
        time_to_next_frame = self._frame_period - time.time() + draw_start_time
        if time_to_next_frame > 0:
            time.sleep(time_to_next_frame)

    def run(self):
        self._air_client.connect()
        self._is_running = True
        while self._is_running:
            self._loop()
        self._air_client.disconnect()

    def stop(self):
        self._is_running = False
