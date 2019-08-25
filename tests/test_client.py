# Allow protected access in tests
# pylint: disable=W0212
import numpy as np
import pytest
import socket
import time
from unittest import mock

import airpixel
from airpixel import client


class TestPixel:
    def test_init(self):
        pixel = client.Pixel(0, 0, 0)

        assert np.array_equal(pixel._values, np.array([0, 0, 0]))

    @pytest.mark.parametrize(
        "colors, expected",
        [
            ((1, 0, 0), "<Pixel:255,000,000>"),
            ((0, 1, 0), "<Pixel:000,255,000>"),
            ((0, 0, 1), "<Pixel:000,000,255>"),
            ((1, 1, 1), "<Pixel:255,255,255>"),
        ],
    )
    def test_repr(self, colors, expected):
        pixel = client.Pixel(*colors)

        assert repr(pixel) == expected

    @pytest.mark.parametrize(
        "colors, expected",
        [
            ((1, 0, 0), np.array([1, 0, 0, 0])),
            ((0, 1, 0), np.array([0, 1, 0, 0])),
            ((0, 0, 1), np.array([0, 0, 1, 0])),
            ((1, 1, 1), np.array([1, 1, 1, 0])),
        ],
    )
    def test_get_rgbw(self, colors, expected):
        pixel = client.Pixel(*colors)

        rgbw = pixel.get_rgbw()

        assert np.array_equal(rgbw, expected)

    @pytest.mark.parametrize(
        "colors, expected",
        [
            ((1, 0, 0), np.array([0, 1, 0, 0])),
            ((0, 1, 0), np.array([1, 0, 0, 0])),
            ((0, 0, 1), np.array([0, 0, 1, 0])),
            ((1, 1, 1), np.array([1, 1, 1, 0])),
        ],
    )
    def test_get_rgbw(self, colors, expected):
        pixel = client.Pixel(*colors)

        rgbw = pixel.get_grbw()

        assert np.array_equal(rgbw, expected)

    @pytest.mark.parametrize(
        "colors, expected",
        [
            ((1, 0, 0), np.array([1, 0, 0])),
            ((0, 1, 0), np.array([0, 1, 0])),
            ((0, 0, 1), np.array([0, 0, 1])),
            ((1, 1, 1), np.array([1, 1, 1])),
        ],
    )
    def test_get_rgb(self, colors, expected):
        pixel = client.Pixel(*colors)

        rgb = pixel.get_rgb()

        assert np.array_equal(rgb, expected)

    @pytest.mark.parametrize(
        "colors, expected",
        [
            ((1, 0, 0), np.array([0, 1, 0])),
            ((0, 1, 0), np.array([1, 0, 0])),
            ((0, 0, 1), np.array([0, 0, 1])),
            ((1, 1, 1), np.array([1, 1, 1])),
        ],
    )
    def test_get_rgb(self, colors, expected):
        pixel = client.Pixel(*colors)

        rgb = pixel.get_grb()

        assert np.array_equal(rgb, expected)

    @pytest.mark.parametrize(
        "colors, color_method, expected",
        [
            ((1, 0.5, 0), client.ColorMethod.RGB, np.array([1, 0.5, 0])),
            ((1, 0.5, 0), client.ColorMethod.RGBW, np.array([1, 0.5, 0, 0])),
            ((1, 0.5, 0), client.ColorMethod.GRB, np.array([0.5, 1, 0])),
            ((1, 0.5, 0), client.ColorMethod.GRBW, np.array([0.5, 1, 0, 0])),
        ],
    )
    def test_get_color(self, colors, color_method, expected):
        pixel = client.Pixel(*colors)

        rgb = pixel.get_colors(color_method)

        assert np.array_equal(rgb, expected)


class TestSafeMessage:
    @staticmethod
    def test_created_empty():
        message = client.SafeMessage()

        with pytest.raises(message.Empty):
            message.consume()

    @staticmethod
    def test_write_and_consume():
        message = client.SafeMessage()

        message.write(b"hello world")
        data = message.consume()

        assert data == b"hello world"
        with pytest.raises(message.Empty):
            message.consume()

    @staticmethod
    def test_write_peek():
        message = client.SafeMessage()

        message.write(b"hello world")
        data = message.peek()

        assert data == b"hello world"
        assert message.consume() == b"hello world"


class TestAirPixelInterface:
    @staticmethod
    def test_show_frame(mock_connector):
        interface = client.AirPixelInterface(mock_connector)

        interface.show_frame([airpixel.Pixel(0, 0, 0), airpixel.Pixel(0, 1, 0)])

        mock_connector.send_bytes.assert_called_with(b"\x00\x00\x00\xFF\x00\x00")


class TestTimeoutTracker:
    @staticmethod
    def test_doesnt_send_when_initialized(
        mock_time, mock_udp_connection, timeout_tracker
    ):
        timeout_tracker.send_heartbeat_if_needed()

        mock_udp_connection.send_bytes_unsafe.assert_not_called()

    @staticmethod
    def test_doesnt_send_early(mock_time, mock_udp_connection, timeout_tracker):
        timeout_tracker.notify_got_message()
        mock_time.advance_seconds(1)

        timeout_tracker.send_heartbeat_if_needed()

        mock_udp_connection.send_bytes_unsafe.assert_not_called()

    @staticmethod
    def test_does_send_after_half(mock_time, mock_udp_connection, timeout_tracker):
        timeout_tracker.notify_got_message()
        mock_time.advance_seconds(2.6)

        timeout_tracker.send_heartbeat_if_needed()

        mock_udp_connection.send_bytes_unsafe.assert_called_once_with(
            client.UDPConstants.HEARTBEAT_FRAME
        )

    @staticmethod
    def test_does_sends_only_once(mock_time, mock_udp_connection, timeout_tracker):
        timeout_tracker.notify_got_message()
        mock_time.advance_seconds(2.6)
        timeout_tracker.send_heartbeat_if_needed()
        mock_udp_connection.send_bytes_unsafe.reset_mock()

        timeout_tracker.send_heartbeat_if_needed()

        mock_udp_connection.send_bytes_unsafe.assert_not_called()

    @staticmethod
    def test_doesnt_sendafter_timeout(mock_time, mock_udp_connection, timeout_tracker):
        timeout_tracker.notify_got_message()
        mock_time.advance_seconds(5.1)

        timeout_tracker.send_heartbeat_if_needed()

        mock_udp_connection.send_bytes_unsafe.assert_not_called()


class TestUDPConnection:
    @staticmethod
    @pytest.mark.timeout(0.3)
    def test_find_remote_ip(mock_time, udp_connection, config):
        udp_connection.mock_search_socket.recvmsg.return_value = (
            config.advertise_message,
            None,
            None,
            ("1.1.1.1", None),
        )

        remote_ip = udp_connection.find_remote_ip()

        assert remote_ip == "1.1.1.1"

    @staticmethod
    @pytest.mark.timeout(0.3)
    def test_find_remote_ip_time_out(mock_time, udp_connection, config):
        udp_connection.mock_search_socket.recvmsg.return_value = (
            b"some-message",
            None,
            None,
            ("1.1.1.1", None),
        )

        with pytest.raises(client.NoBroadcasterFoundError):
            udp_connection.find_remote_ip(timeout=-1)

    @staticmethod
    @pytest.mark.timeout(0.3)
    def test_connect(mock_time, udp_connection, config):
        udp_connection.mock_search_socket.recvmsg.return_value = (
            config.advertise_message,
            None,
            None,
            ("1.1.1.1", None),
        )
        udp_connection.mock_receive_socket.getsockname.return_value = ("", 255)
        udp_connection.mock_receive_socket.recvmsg.return_value = (
            client.UDPConstants.CONNECT_FRAME,
            None,
            None,
            ("1.1.1.1", 123),
        )

        udp_connection.connect()

        udp_connection.mock_send_socket.sendto.assert_called_once_with(
            client.UDPConstants.CONNECT_FRAME + b"\x00\x00\x00\xFF",
            ("1.1.1.1", client.UDPConfig.remote_port),
        )

