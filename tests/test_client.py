# Allow protected access in tests
# pylint: disable=W0212
import numpy as np
import pytest
import socket
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
