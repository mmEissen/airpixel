# Allow protected access in tests
# pylint: disable=W0212
import numpy as np
import pytest
import socket
from unittest import mock

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


class TestAirDetective:
    def test_init(self):
        air_detective = client.AirDetective(1)

        assert air_detective._port == 1

    @pytest.mark.timeout(0.1)
    def test_find_ring_ip(self, air_detective):
        mock_socket = air_detective._socket
        mock_socket.recvmsg.side_effect = [
            (b"something", None, None, ("0.0.0.0", None)),
            (b"LEDRing\n", None, None, ("1.1.1.1", None)),
        ]

        ip_address = air_detective.find_remote_ip()

        assert ip_address == "1.1.1.1"


class TestConnectionSupervisor:
    def test_init(self, connection_supervisor):
        assert connection_supervisor.is_connected() is False

    def test_setup(self, connection_supervisor):
        connection_supervisor._setup()

        assert connection_supervisor._is_running
        assert connection_supervisor._receive_socket.bind.called_once_with(("", 50000))

    def test_send_in_correct_order(self, connection_supervisor):
        connection_supervisor._setup()
        connection_supervisor.send(b"first")
        connection_supervisor.send(b"second")
        connection_supervisor.send(b"third")
        address = connection_supervisor._remote_address

        connection_supervisor._loop()
        connection_supervisor._loop()
        connection_supervisor._loop()

        sendto_mock = connection_supervisor._send_socket.sendto
        sendto_mock.assert_has_calls(
            [
                mock.call(b"first", address),
                mock.call(b"second", address),
                mock.call(b"third", address),
            ]
        )
        assert sendto_mock.call_count == 3
