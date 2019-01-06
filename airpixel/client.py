import abc
import heapq
import socket
import enum
import time
import threading
import queue
import typing as t

import numpy as np

from . import gamma_table


class AirClientError(Exception):
    pass


class ConnectionFailedError(AirClientError):
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
    def __init__(self, red, green, blue) -> None:
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

    def get_rgbw(self):
        # For now just r, g, b, 0.
        # This might have a better solution:
        # http://www.mirlab.org/conference_papers/International_Conference/ICASSP%202014/papers/p1214-lee.pdf
        return np.append(self._values, [0])

    def get_grbw(self):
        red, green, blue, white = self.get_rgbw()
        return np.array((green, red, blue, white))

    def get_rgb(self):
        return self._values

    def get_grb(self):
        red, green, blue = self.get_rgb()
        return np.array((green, red, blue))

    def get_colors(self, color_method):
        return self._color_method_map[color_method]()


class LoopingThread(threading.Thread, abc.ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_running = False

    @abc.abstractmethod
    def loop(self):
        pass

    def setup(self):
        self._is_running = True

    def tear_down(self):
        pass

    def run(self):
        self.setup()
        while self._is_running:
            self.loop()
        self.tear_down()

    def stop(self):
        self._is_running = False


class AirDetective:
    def __init__(self, port: int) -> None:
        self._port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def find_remote_ip(self):
        with self._socket:
            self._socket.bind(("", self._port))
            message = b""
            while message != b"LEDRing\n":
                message, _, _, (ip_address, _) = self._socket.recvmsg(32)
            return ip_address


class AbstractClient(abc.ABC):
    def __init__(self, num_leds, color_method) -> None:
        self.num_leds = num_leds
        self.color_method = color_method
        self._pixels = self.clear_frame()

    def __repr__(self):
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
    def __init__(self, timeout, send_heartbeat_fnc):
        self._timeout = timeout
        self._last_message = float("+inf")
        self._heartbeats_sent = 0
        self._send_heartbeat = send_heartbeat_fnc

    def is_timed_out(self):
        return self._last_message + self._timeout < time.time()

    def notify_got_message(self):
        self._last_message = time.time()
        self._heartbeats_sent = 0

    def send_heartbeat_if_needed(self):
        next_beat = (
            1 - 1 / 2 ** (self._heartbeats_sent + 1)
        ) * self._timeout + self._last_message
        if time.time() > next_beat:
            self._send_heartbeat()
            self._heartbeats_sent += 1


class ConnectionSupervisor(LoopingThread):
    _buffer_size = 4096
    _socket_timeout = 0.01

    def __init__(self, remote_address, local_address, timeout, heartbeat_message):
        super().__init__(name="connection-supervisor-thread")
        self._is_running = False
        self._remote_address = remote_address
        self._local_address = local_address

        self._send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._receive_socket.settimeout(self._socket_timeout)

        self._send_buffer = queue.Queue()
        self._receive_buffer = queue.Queue()

        self._heartbeat_message = heartbeat_message
        self._timeout_tracker = TimeoutTracker(timeout, self._send_heartbeat)

    def _send_heartbeat(self):
        self._send_raw(self._heartbeat_message)

    def _check_timeout(self):
        if self._timeout_tracker.is_timed_out():
            self.stop()

    def _send_raw(self, message):
        self._send_socket.sendto(message, self._remote_address)

    def _read_message_to_buffer(self):
        try:
            message, _, _, (ip_address, _) = self._receive_socket.recvmsg(
                self._buffer_size
            )
        except socket.timeout:
            return
        if ip_address == self._remote_address[0]:
            self._receive_buffer.put_nowait((time.time(), message))
            self._timeout_tracker.notify_got_message()

    def _send_message_from_buffer(self):
        try:
            message = self._send_buffer.get_nowait()
        except queue.Empty:
            return False
        self._send_raw(message)
        return True

    def _flush_send_buffer(self):
        while self._send_message_from_buffer():
            pass

    def send(self, message):
        self._send_buffer.put_nowait(message)

    def incoming_messages(self):
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

    def wait_for_message(self, timeout):
        try:
            return self._receive_buffer.get(True, timeout)
        except queue.Empty:
            return None

    def setup(self):
        self._is_running = True
        self._receive_socket.bind(self._local_address)

    def loop(self):
        self._read_message_to_buffer()
        self._send_message_from_buffer()
        self._check_timeout()
        self._timeout_tracker.send_heartbeat_if_needed()

    def tear_down(self):
        self._flush_send_buffer()

    def run(self):
        with self._receive_socket, self._send_socket:
            super().run()

    def is_connected(self):
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
        self, remote_port, receive_port, num_leds, color_method=ColorMethod.GRBW
    ):
        super().__init__(num_leds, color_method)
        if remote_port == receive_port:
            raise ValueError("remote_port must be different from receive_port!")
        self._remote_port = remote_port
        self._receive_port = receive_port
        self.frame_number = 1
        self._connection = self._make_connection_supervisor("")

    def _make_connection_supervisor(self, remote_ip):
        return ConnectionSupervisor(
            (remote_ip, self._remote_port),
            ("", self._receive_port),
            self._timeout_seconds,
            self._heartbeat_frame,
        )

    def is_connected(self) -> bool:
        return self._connection.is_connected()

    def _attempt_connect(self):
        port_as_bytes = self._receive_port.to_bytes(4, self._encoding_byteorder)
        self._connection.send(self._connect_frame + port_as_bytes)
        _, message = self._connection.wait_for_message(self._timeout_seconds)
        return message == self._connect_frame

    def connect(self) -> None:
        remote_address = AirDetective(self._remote_port).find_remote_ip()
        self._connection = self._make_connection_supervisor(remote_address)
        self._connection.start()

        for _ in range(self._connect_attempts):
            if self._attempt_connect():
                return
        raise ConnectionFailedError("Failed to connect!")

    def get_confirmed_frames(self):
        messages = self._connection.incoming_messages()
        return (
            (timestamp, int.from_bytes(message, self._encoding_byteorder))
            for timestamp, message in messages
        )

    def disconnect(self) -> None:
        self._connection.send(self._disconnect_frame)
        self._connection.stop()
        self._connection.join()

    def _pixel_list(self):
        return [pixel.get_colors(self.color_method) for pixel in self._pixels]

    def _raw_data(self):
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


class RenderLoop(LoopingThread):
    def __init__(self, air_client, update_fnc, max_framerate=120):
        super().__init__(name="render-loop-thread")
        self._frame_period = 1 / max_framerate
        self._update_fnc = update_fnc
        self._is_running = False
        self._air_client = air_client
        self._sent_frames = {}
        self._frame_deltas = []
        self._delta_sum = 0
        self.avg_frame_time = 0

    def loop(self):
        draw_start_time = time.time()
        self._sent_frames[self._air_client.frame_number] = draw_start_time
        new_frame = self._update_fnc(draw_start_time)
        self._air_client.set_frame(new_frame)
        self._air_client.show()
        self._track_performance(draw_start_time)
        time_to_next_frame = self._frame_period - time.time() + draw_start_time
        if time_to_next_frame > 0:
            time.sleep(time_to_next_frame)

    def _track_performance(self, now):
        for timestamp, frame in self._air_client.get_confirmed_frames():
            sent_time = self._sent_frames.pop(frame, None)
            if sent_time is None:
                continue
            delta = timestamp - sent_time
            heapq.heappush(self._frame_deltas, (timestamp, delta))
            self._delta_sum += delta
        while self._frame_deltas and self._frame_deltas[0][0] < now - 1:
            _, delta = heapq.heappop(self._frame_deltas)
            self._delta_sum -= delta
        if self._frame_deltas:
            self.avg_frame_time = self._delta_sum / len(self._frame_deltas)
        else:
            self.avg_frame_time = 0

    def setup(self):
        self._air_client.connect()
        return super().setup()

    def tear_down(self):
        self._air_client.disconnect()
        return super().tear_down()
