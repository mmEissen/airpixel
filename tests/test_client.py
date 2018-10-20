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


class TestAirDetective:
    def test_init(self):
        air_detective = client.AirDetective(1)

        assert air_detective._port == 1
        assert air_detective._socket is None


    def test_bind_socket(self, air_detective, mock_socket):
        mock_socket_object = mock.MagicMock()
        mock_socket.return_value = mock_socket_object

        air_detective._bind_socket()

        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
        assert air_detective._socket is mock_socket_object
        mock_socket_object.bind.assert_called_once_with(("", 1))

    def test_binding_with_socket_creation_failure(self, air_detective, mock_socket):
        mock_socket.side_effect = OSError

        with pytest.raises(client.AirClientConnectionError):
            air_detective._bind_socket()

        assert air_detective._socket is None

    def test_binding_with_socket_binding_failure(self, air_detective, mock_socket):
        mock_socket_object = mock.MagicMock()
        mock_socket.return_value = mock_socket_object
        mock_socket_object.bind.side_effect = OSError

        with pytest.raises(client.AirClientConnectionError):
            air_detective._bind_socket()

        assert air_detective._socket is None
        mock_socket_object.close.assert_called_once()
