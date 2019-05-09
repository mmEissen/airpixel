import abc
import socket
import enum
import time
import threading
import queue
import typing as t

import numpy as np

from . import gamma_table


T = t.TypeVar("T")  # pylint: disable=invalid-name


class QueueType(queue.Queue, t.Generic[T]):
    def qsize(self) -> int:
        pass

    def put(
        self, item: T, block: bool = True, timeout: t.Optional[float] = None
    ) -> None:
        pass

    def put_nowait(self, item: T) -> None:
        pass

    def get(self, block: bool = True, timeout: t.Optional[float] = None) -> T:
        pass

    def get_nowait(self) -> T:
        pass


class AirClientError(Exception):
    pass


class ConnectionFailedError(AirClientError):
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


class AbstractClient(abc.ABC):
    def __init__(self, num_leds: int, color_method: ColorMethod) -> None:
        self.num_leds = num_leds
        self.color_method = color_method
        self._pixels = self.clear_frame()

    def __repr__(self) -> str:
        return "{}<{}LEDs>".format(self.__class__.__name__, self.num_leds)

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


class TimeoutTracker:
    def __init__(self, timeout: float, send_heartbeat_fnc: t.Callable[[], None]):
        self.timeout = timeout
        self._last_message = float("+inf")
        self._heartbeats_sent = 0
        self._send_heartbeat = send_heartbeat_fnc

    def is_timed_out(self) -> bool:
        return self._last_message + self.timeout < time.time()

    def notify_got_message(self) -> None:
        self._last_message = time.time()
        self._heartbeats_sent = 0

    def send_heartbeat_if_needed(self) -> None:
        next_beat = (
            1 - 1 / 2 ** (self._heartbeats_sent + 1)
        ) * self.timeout + self._last_message
        if time.time() > next_beat:
            self._send_heartbeat()
            self._heartbeats_sent += 1


class ConnectionSupervisor(LoopingThread):
    _socket_buffer_size = 4096
    _receive_buffer_size = 1024
    _socket_timeout = 0.01
    _local_ip = ""

    def __init__(
        self,
        remote_port: int,
        receive_port: int,
        timeout: float,
        heartbeat_message: bytes,
        search_timeout: float,
    ):
        super().__init__(name="connection-supervisor-thread", daemon=True)
        self.remote_ip = ""
        self._remote_port = remote_port
        self._receive_port = receive_port

        self._search_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._search_socket.settimeout(self._socket_timeout)
        self._send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._receive_socket.settimeout(self._socket_timeout)

        self._send_buffer: QueueType[bytes] = t.cast(QueueType[bytes], queue.Queue())
        self._receive_buffer: QueueType[t.Tuple[float, bytes]] = t.cast(
            QueueType[t.Tuple[float, bytes]], queue.Queue(self._receive_buffer_size)
        )

        self._heartbeat_message = heartbeat_message
        self._timeout_tracker = TimeoutTracker(timeout, self._send_heartbeat)
        self._search_timeout = search_timeout

    def _send_heartbeat(self) -> None:
        self._send_raw(self._heartbeat_message)

    def _check_timeout(self) -> None:
        if self._timeout_tracker.is_timed_out():
            self.stop()

    def _send_raw(self, message: bytes) -> None:
        self._send_socket.sendto(message, (self.remote_ip, self._remote_port))

    def _read_message_to_buffer(self) -> None:
        try:
            message, _, _, (ip_address, _) = self._receive_socket.recvmsg(
                self._socket_buffer_size
            )
        except socket.timeout:
            return
        if ip_address != self.remote_ip:
            return
        try:
            self._receive_buffer.put_nowait((time.time(), message))
        except queue.Full:
            self._receive_buffer.get_nowait()
            self._receive_buffer.put_nowait((time.time(), message))
        self._timeout_tracker.notify_got_message()

    def _send_message_from_buffer(self) -> bool:
        send = False
        while True:
            try:
                message = self._send_buffer.get_nowait()
            except queue.Empty:
                break
            else:
                send = True
        if send:
            self._send_raw(message)
        return send

    def _flush_send_buffer(self) -> None:
        while self._send_message_from_buffer():
            pass

    def _find_remote_ip(self, timeout: float = -1, broadcaster_message: bytes = b"LEDRing\n") -> None:
        with self._search_socket:
            self._search_socket.bind(("", self._remote_port))
            search_start_time = time.time()
            while True:
                try:
                    message, _, _, (ip_address, _) = self._search_socket.recvmsg(32)
                except socket.timeout:
                    pass
                else:
                    if message == broadcaster_message:
                        self.remote_ip = ip_address
                        return
                if timeout >= 0 and time.time() - search_start_time > timeout:
                    raise NoBroadcasterFoundError()

    def send(self, message: bytes) -> None:
        self._send_buffer.put_nowait(message)

    def incoming_messages(self) -> t.List[t.Tuple[float, bytes]]:
        """Consume the receive buffer and return the messages.

        If there are new messages added to the queue while this funciton is being
        processed, they will not be returned. This ensures that this terminates in
        a timely manner.
        """
        approximate_messages = self._receive_buffer.qsize()
        messages = []
        for _ in range(approximate_messages):
            try:
                messages.append(self._receive_buffer.get_nowait())
            except queue.Empty:
                break
        return messages

    def wait_for_message(self, timeout: float) -> t.Optional[t.Tuple[float, bytes]]:
        try:
            return self._receive_buffer.get(True, timeout)
        except queue.Empty:
            return None

    def setup(self) -> None:
        super().setup()
        self._find_remote_ip(self._search_timeout)
        self._receive_socket.bind((self._local_ip, self._receive_port))

    def loop(self) -> None:
        self._read_message_to_buffer()
        self._send_message_from_buffer()
        self._check_timeout()
        self._timeout_tracker.send_heartbeat_if_needed()

    def tear_down(self) -> None:
        self._flush_send_buffer()

    def run(self) -> None:
        with self._receive_socket, self._send_socket:
            super().run()

    def is_connected(self) -> bool:
        return self._is_running


class AirClient(AbstractClient):
    _encoding_byteorder = "big"
    _timeout_seconds = 5
    _frame_number_bytes = 8
    _connect_attempts = 3
    _disconnect_frame = (2 ** (8 * _frame_number_bytes) - 1).to_bytes(
        _frame_number_bytes, _encoding_byteorder
    )
    _connect_frame = (2 ** (8 * _frame_number_bytes) - 2).to_bytes(
        _frame_number_bytes, _encoding_byteorder
    )
    _heartbeat_frame = (2 ** (8 * _frame_number_bytes) - 3).to_bytes(
        _frame_number_bytes, _encoding_byteorder
    )

    def __init__(
        self,
        remote_port: int,
        receive_port: int,
        num_leds: int,
        color_method: ColorMethod = ColorMethod.GRBW,
        search_timeout: float = -1,
    ):
        super().__init__(num_leds, color_method)
        if remote_port == receive_port:
            raise ValueError("remote_port must be different from receive_port!")
        self._remote_port = remote_port
        self._receive_port = receive_port
        self.frame_number = 1
        self._search_timeout = search_timeout
        self._connection = self._make_connection_supervisor()

    def _make_connection_supervisor(self) -> ConnectionSupervisor:
        return ConnectionSupervisor(
            self._remote_port,
            self._receive_port,
            self._timeout_seconds,
            self._heartbeat_frame,
            self._search_timeout,
        )

    def is_connected(self) -> bool:
        return self._connection.is_connected()

    def _attempt_connect(self) -> bool:
        port_as_bytes = self._receive_port.to_bytes(4, self._encoding_byteorder)
        self._connection.send(self._connect_frame + port_as_bytes)
        timed_message = self._connection.wait_for_message(self._timeout_seconds)
        if timed_message is None:
            return False
        _, message = timed_message
        return message == self._connect_frame

    def connect(self) -> None:
        self._connection = self._make_connection_supervisor()
        self._connection.start()

        for _ in range(self._connect_attempts):
            if self._attempt_connect():
                self.frame_number = 1
                return
        raise ConnectionFailedError("Failed to connect!")

    def disconnect(self) -> None:
        self._connection.send(self._disconnect_frame)
        self._connection.stop()
        self._connection.join()

    def _pixel_list(self) -> t.List[np.ndarray]:
        return [pixel.get_colors(self.color_method) for pixel in self._pixels]

    def _raw_data(self) -> bytes:
        pixels = np.concatenate(self._pixel_list())
        pixels = gamma_table.GAMMA_TABLE[(pixels * 255).astype("uint8")]
        return self.frame_number.to_bytes(
            self._frame_number_bytes, byteorder=self._encoding_byteorder
        ) + bytes(pixels)

    def show(self) -> None:
        if not self.is_connected():
            raise NotConnectedError("Client must be connected before calling show()!")
        self._connection.send(self._raw_data())
        self.frame_number += 1

    def show_frame(self, frame: t.List[Pixel]) -> None:
        self.set_frame(frame)
        self.show()
