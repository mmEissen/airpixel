import pytest

from airpixel import monitoring


@pytest.fixture(name="stream_id")
def f_stream_id():
    return "some_stream_id"


@pytest.fixture(name="data")
def f_data():
    return b"some random data"


@pytest.fixture(name="raw_package")
def f_raw_package(stream_id, data):
    stream_id_bytes = bytes(stream_id, "utf-8")
    stream_id_header = (
        monitoring.MonitoringPackage.STREAM_ID_SIZE - len(stream_id_bytes)
    ) * b"\x00" + stream_id_bytes
    return stream_id_header + data


@pytest.fixture(name="monitoring_package")
def f_monitoring_package(stream_id, data):
    return monitoring.MonitoringPackage(stream_id, data)
