import pytest

from airpixel import monitoring


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
