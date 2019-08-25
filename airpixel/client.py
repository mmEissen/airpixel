import abc
import dataclasses
import socket
import enum
import time
import threading
import typing as t

import numpy as np

from . import gamma_table


class AirClientError(Exception):
    pass


class ConnectionFailedError(AirClientError):
    pass


class ReceiveTimeoutError(AirClientError):
    pass


class NoBroadcasterFoundError(ConnectionFailedError):
    pass


class ThreadUnresponsiveError(AirClientError):
    pass


class NotConnectedError(AirClientError):
    pass


class PixelOutOfRangeError(IndexError):
    pass


class ColorMethod(enum.Enum):
    RGB = "RGB"
    RGBW = "RGBW"
    GRB = "GRB"
    GRBW = "GRBW"


class Pixel:
    def __init__(self, red: float, green: float, blue: float) -> None:
        self._values = np.array((red, green, blue))
        self._color_method_map = {
            ColorMethod.RGB: self.get_rgb,
            ColorMethod.RGBW: self.get_rgbw,
            ColorMethod.GRB: self.get_grb,
            ColorMethod.GRBW: self.get_grbw,
        }

    def __repr__(self) -> str:
        red, green, blue = (int(c) for c in self.get_rgb() * 255)
        return "<{}:{:0>3},{:0>3},{:0>3}>".format(
            self.__class__.__name__, red, green, blue
        )

    def get_rgbw(self) -> np.ndarray:
        # For now just r, g, b, 0.
        # This might have a better solution:
        # http://www.mirlab.org/conference_papers/International_Conference/ICASSP%202014/papers/p1214-lee.pdf
        return np.append(self._values, [0])

    def get_grbw(self) -> np.ndarray:
        red, green, blue, white = self.get_rgbw()
        return np.array((green, red, blue, white))

    def get_rgb(self) -> np.ndarray:
        return self._values

    def get_grb(self) -> np.ndarray:
        red, green, blue = self.get_rgb()
        return np.array((green, red, blue))

    def get_colors(self, color_method: ColorMethod) -> np.ndarray:
        return self._color_method_map[color_method]()


class LoopingThread(threading.Thread, abc.ABC):
    def __init__(self, *args: t.Any, **kwargs: t.Any):
        super().__init__(*args, **kwargs)
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


class PixelConnector(abc.ABC):
    @abc.abstractmethod
    def send_bytes(self, message: bytes) -> None:
        pass


class AirPixelInterface:
    def __init__(
        self, connector: PixelConnector, color_method: ColorMethod = ColorMethod.GRB
    ) -> None:
        self.color_method = color_method
        self.connector = connector

    def __repr__(self) -> str:
        return "{}<{}-LEDs>".format(self.__class__.__name__, self.color_method.value)

    def show_frame(self, frame: t.List[Pixel]) -> None:
        raw_pixels = np.concatenate(
            [pixel.get_colors(self.color_method) for pixel in frame]
        )
        raw_pixels = gamma_table.GAMMA_TABLE[(raw_pixels * 255).astype("uint8")]
        self.connector.send_bytes(bytes(raw_pixels))


class SafeMessage:
    class Empty(Exception):
        pass

    def __init__(self) -> None:
        super().__init__()
        self._message = b""
        self._lock = threading.Lock()
        self._message_ready = False

    def write(self, message: bytes) -> None:
        with self._lock:
            self._message_ready = True
            self._message = message

    def consume(self) -> bytes:
        with self._lock:
            message = self._peek_no_lock()
            self._message_ready = False
            return message

    def peek(self) -> bytes:
        with self._lock:
            return self._peek_no_lock()

    def _peek_no_lock(self) -> bytes:
        if not self._message_ready:
            raise self.Empty
        return self._message


@dataclasses.dataclass
class UDPConfig:
    timeout_ms: int = 5000
    advertise_delay_ms: int = 100
    remote_port: int = 50000
    advertise_port: int = 50000
    advertise_message: bytes = b"LEDRing\n"


class UDPConstants:
    ENCODING_BYTEORDER = "big"
    FRAME_NUMBER_BYTES = 8
    BITS_IN_BYTE = 8
    DISCONNECT_FRAME = (2 ** (BITS_IN_BYTE * FRAME_NUMBER_BYTES) - 1).to_bytes(
        FRAME_NUMBER_BYTES, ENCODING_BYTEORDER
    )
    CONNECT_FRAME = (2 ** (BITS_IN_BYTE * FRAME_NUMBER_BYTES) - 2).to_bytes(
        FRAME_NUMBER_BYTES, ENCODING_BYTEORDER
    )
    HEARTBEAT_FRAME = (2 ** (BITS_IN_BYTE * FRAME_NUMBER_BYTES) - 3).to_bytes(
        FRAME_NUMBER_BYTES, ENCODING_BYTEORDER
    )
    MAX_PACKET_SIZE = 65507


class UDPConnection(PixelConnector, LoopingThread):
    RESPONSE_TIMEOUT = 1

    def __init__(self, config: t.Optional[UDPConfig] = None):
        super().__init__(name="udp-connection", daemon=True)
        self._message = SafeMessage()
        self._receive_socket = self.make_receive_socket()
        self._send_socket = self.make_send_socket()
        self._timeout_tracker = TimeoutTracker(self)
        self.config = config or UDPConfig()
        self.remote_ip = ""
        self.frame_number = 1

    @staticmethod
    def make_receive_socket() -> socket.socket:
        socket_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_.settimeout(0)
        return socket_

    @staticmethod
    def make_send_socket() -> socket.socket:
        return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def make_search_socket(self) -> socket.socket:
        socket_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_.settimeout(self.RESPONSE_TIMEOUT)
        return socket_

    def connect(self) -> None:
        self.remote_ip = self.find_remote_ip(self.config.advertise_delay_ms / 1000 * 3)
        self._receive_socket = self.make_receive_socket()
        self._receive_socket.bind((self.remote_ip, 0))
        receive_port = self._receive_socket.getsockname()[1]
        port_as_bytes = receive_port.to_bytes(4, UDPConstants.ENCODING_BYTEORDER)
        self.send_bytes_unsafe(UDPConstants.CONNECT_FRAME + port_as_bytes)
        try:
            self.receive_message(timeout=self.RESPONSE_TIMEOUT)
        except ReceiveTimeoutError as error:
            raise ConnectionFailedError from error

    def find_remote_ip(self, timeout: t.Optional[float] = None) -> str:
        search_socket = self.make_search_socket()
        with search_socket:
            search_socket.bind(("", self.config.advertise_port))
            search_start_time = time.time()
            while True:
                try:
                    message, _, _, (ip_address, _) = search_socket.recvmsg(
                        UDPConstants.MAX_PACKET_SIZE
                    )
                except BlockingIOError:
                    pass
                else:
                    if message == self.config.advertise_message:
                        return ip_address
                if timeout is not None and time.time() - search_start_time > timeout:
                    raise NoBroadcasterFoundError()

    def receive_message(self, timeout: t.Optional[float] = 0) -> bytes:
        self._receive_socket.settimeout(timeout)
        try:
            message, *_ = self._receive_socket.recvmsg(UDPConstants.MAX_PACKET_SIZE)
        except (socket.timeout, BlockingIOError) as error:
            raise ReceiveTimeoutError from error
        else:
            self._timeout_tracker.notify_got_message()
            return message

    def send_bytes_unsafe(self, message: bytes) -> None:
        self._send_socket.sendto(message, (self.remote_ip, self.config.remote_port))

    def send_bytes(self, message: bytes) -> None:
        self._message.write(message)

    def send_message(self) -> None:
        try:
            message = self._message.consume()
        except self._message.Empty:
            return
        frame_number = self.frame_number.to_bytes(
            UDPConstants.FRAME_NUMBER_BYTES, byteorder=UDPConstants.ENCODING_BYTEORDER
        )
        self.send_bytes_unsafe(frame_number + message)

    def is_connected(self) -> bool:
        return not self._timeout_tracker.is_timed_out()

    def loop(self) -> None:
        if not self.is_connected():
            try:
                self.connect()
            except ConnectionFailedError:
                return
        self.send_message()
        try:
            self.receive_message()
        except ReceiveTimeoutError:
            pass


class TimeoutTracker:
    def __init__(self, udp_connection: UDPConnection):
        self._last_message = float("-inf")
        self._heartbeats_sent = 0
        self._udp_connection = udp_connection

    def is_timed_out(self) -> bool:
        return (
            self._last_message + self._udp_connection.config.timeout_ms / 1000
            < time.time()
        )

    def notify_got_message(self) -> None:
        self._last_message = time.time()
        self._heartbeats_sent = 0

    def send_heartbeat_if_needed(self) -> None:
        next_beat = (
            1 - 1 / 2 ** (self._heartbeats_sent + 1)
        ) * self._udp_connection.config.timeout_ms / 1000 + self._last_message
        if time.time() > next_beat and not self.is_timed_out():
            self._udp_connection.send_bytes_unsafe(UDPConstants.HEARTBEAT_FRAME)
            self._heartbeats_sent += 1


class UDPAirPixel(AirPixelInterface):
    def __init__(
        self,
        color_method: ColorMethod = ColorMethod.GRB,
        udp_config: t.Optional[UDPConfig] = None,
    ) -> None:
        udp_connection = UDPConnection(udp_config)
        udp_connection.start()
        super().__init__(udp_connection, color_method=color_method)
