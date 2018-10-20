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
