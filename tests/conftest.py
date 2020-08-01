from unittest import mock

import pytest

from airpixel import monitoring


@pytest.fixture(name="clock")
def f_clock():
    class MockClock:
        def __init__(self):
            self.time = 1_000_000_000

        def __call__(self):
            return self.time

    with mock.patch("time.time", new=MockClock()) as clock:
        yield clock


@pytest.fixture(name="udp_port")
def f_udp_port():
    return 50001
