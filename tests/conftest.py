from unittest import mock

import pytest

from airpixel import client


class MockConnectionSupervisor(client.ConnectionSupervisor):
    def __init__(
        self, remote_port, receive_port, timeout, heartbeat_message, search_timeout
    ):
        super().__init__(
            remote_port, receive_port, timeout, heartbeat_message, search_timeout
        )
        self.search_socket = self._search_socket
        self.receive_socket = self._receive_socket
        self.send_socket = self._send_socket


@pytest.fixture
def mock_socket():
    def magic_mock_factory(*args, **kwargs):
        return mock.MagicMock()

    with mock.patch("socket.socket", new=magic_mock_factory):
        yield


@pytest.fixture
def remote_address():
    return "1.1.1.1", 50000


@pytest.fixture
def connection_supervisor(mock_socket, remote_address):
    remote_ip, remote_port = remote_address
    supervisor = MockConnectionSupervisor(
        remote_port, remote_port + 1, 0.02, b"heartbeat", -1
    )
    supervisor.search_socket.recvmsg.return_value = (
        b"LEDRing\n",
        mock.MagicMock(),
        mock.MagicMock(),
        (remote_ip, mock.MagicMock()),
    )
    supervisor.receive_socket.recvmsg.return_value = (
        mock.MagicMock(),
        mock.MagicMock(),
        mock.MagicMock(),
        (mock.MagicMock(), mock.MagicMock()),
    )
    return supervisor
