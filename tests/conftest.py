from unittest import mock

import pytest

from airpixel import client


@pytest.fixture
def mock_socket():
    with mock.patch("socket.socket") as mocket:
        yield mocket


@pytest.fixture
def air_detective(mock_socket):
    return client.AirDetective(1)


@pytest.fixture
def connection_supervisor(mock_socket):
    connection_supervisor = client.ConnectionSupervisor(
        ("1.1.1.1", 50000), ("", 50001), 5, b"heartbeat"
    )
    connection_supervisor._receive_socket.recvmsg.return_value = (
        mock.MagicMock(),
        mock.MagicMock(),
        mock.MagicMock(),
        (mock.MagicMock(), mock.MagicMock()),
    )
    return connection_supervisor
