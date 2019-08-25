from unittest import mock

import pytest

from airpixel import client


@pytest.fixture
def mock_connector():
    return mock.MagicMock(spec=client.PixelConnector)
