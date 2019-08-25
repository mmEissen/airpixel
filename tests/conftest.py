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
    def make_socket(self):
        return mock.MagicMock(spec=socket.socket)


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
    return MockUDPConnection(config)


@pytest.fixture
def mock_udp_connection(config):
    return mock.MagicMock(spec=client.UDPConnection, config=config)


@pytest.fixture
def timeout_tracker(mock_udp_connection):
    return client.TimeoutTracker(mock_udp_connection)
