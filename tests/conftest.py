import socket
from unittest import mock

import pytest

from airpixel import client


class MockTime:
    def __init__(self):
        self.now = 1_500_000_000.0

    def advance_seconds(self, seconds):
        self.now += seconds

    def __call__(self):
        return self.now


class MockUDPConnection(client.UDPConnection):
    def __init__(
        self,
        *args,
        mock_receive_socket=None,
        mock_send_socket=None,
        mock_search_socket=None,
        **kwargs,
    ):
        self.mock_receive_socket = mock_receive_socket
        self.mock_send_socket = mock_send_socket
        self.mock_search_socket = mock_search_socket
        super().__init__(*args, **kwargs)

    def make_send_socket(self):
        return self.mock_send_socket

    def make_receive_socket(self):
        return self.mock_receive_socket

    def make_search_socket(self):
        return self.mock_search_socket


@pytest.fixture
def mock_connector():
    return mock.MagicMock(spec=client.PixelConnector)


@pytest.fixture
def config():
    return client.UDPConfig()


@pytest.fixture
def mock_time():
    time = MockTime()
    with mock.patch("time.time", time):
        yield time


@pytest.fixture
def udp_connection(config):
    connection = MockUDPConnection(
        config,
        mock_receive_socket=mock.MagicMock(spec=socket.socket),
        mock_send_socket=mock.MagicMock(spec=socket.socket),
        mock_search_socket=mock.MagicMock(spec=socket.socket),
    )
    return connection


@pytest.fixture
def mock_udp_connection(config):
    return mock.MagicMock(spec=client.UDPConnection, config=config)


@pytest.fixture
def timeout_tracker(mock_udp_connection):
    return client.TimeoutTracker(mock_udp_connection)
