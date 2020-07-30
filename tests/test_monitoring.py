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


class TestMonitoringPackage:
    @staticmethod
    def test_from_bytes(raw_package, monitoring_package):
        package = monitoring.MonitoringPackage.from_bytes(raw_package)

        assert package == monitoring_package

    @staticmethod
    @pytest.mark.parametrize(
        "raw_package",
        [
            b"",
            b"x" * (monitoring.MonitoringPackage.STREAM_ID_SIZE - 1),
            b"\x00" * monitoring.MonitoringPackage.STREAM_ID_SIZE,
        ],
    )
    def test_from_bytes_for_invalid_header(raw_package):
        with pytest.raises(monitoring.PackageParsingError):
            monitoring.MonitoringPackage.from_bytes(raw_package)

    @staticmethod
    def test_to_bytes(raw_package, monitoring_package):
        raw_bytes = monitoring_package.to_bytes()

        assert raw_package == raw_bytes

    @staticmethod
    @pytest.mark.parametrize(
        "stream_id",
        [
            "x" * (monitoring.MonitoringPackage.STREAM_ID_SIZE + 1),
            "🐍" * monitoring.MonitoringPackage.STREAM_ID_SIZE,
            "",
        ],
    )
    def test_to_bytes_for_invalid_stream_id(monitoring_package):
        with pytest.raises(monitoring.PackageSerializationError):
            monitoring_package.to_bytes()
