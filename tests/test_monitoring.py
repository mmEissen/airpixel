from unittest import mock

import pytest

from airpixel import monitoring


@pytest.fixture(name="ipv4_address")
def f_ipv4_address():
    return "192.168.2.100"


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
        monitoring.Package.STREAM_ID_SIZE - len(stream_id_bytes)
    ) * b"\x00" + stream_id_bytes
    return stream_id_header + data


@pytest.fixture(name="package")
def f_package(stream_id, data):
    return monitoring.Package(stream_id, data)


class TestPackage:
    @staticmethod
    def test_from_bytes(raw_package, package):
        package = monitoring.Package.from_bytes(raw_package)

        assert package == package

    @staticmethod
    @pytest.mark.parametrize(
        "raw_package",
        [
            b"",
            b"x" * (monitoring.Package.STREAM_ID_SIZE - 1),
            b"\x00" * monitoring.Package.STREAM_ID_SIZE,
        ],
    )
    def test_from_bytes_for_invalid_header(raw_package):
        with pytest.raises(monitoring.PackageParsingError):
            monitoring.Package.from_bytes(raw_package)

    @staticmethod
    def test_to_bytes(raw_package, package):
        raw_bytes = package.to_bytes()

        assert raw_package == raw_bytes

    @staticmethod
    @pytest.mark.parametrize(
        "stream_id",
        [
            "x" * (monitoring.Package.STREAM_ID_SIZE + 1),
            "🐍" * monitoring.Package.STREAM_ID_SIZE,
            "",
        ],
    )
    def test_to_bytes_for_invalid_stream_id(package):
        with pytest.raises(monitoring.PackageSerializationError):
            package.to_bytes()


@pytest.fixture(name="mock_socket")
def f_mock_socket():
    return mock.MagicMock()


@pytest.fixture(name="monitoring_server")
def f_monitoring_server(mock_socket, clock):
    monitoring_server = monitoring.Server()
    monitoring_server.socket = mock_socket
    return monitoring_server


@pytest.fixture(name="address")
def f_address(ipv4_address, udp_port):
    return (ipv4_address, udp_port)


@pytest.fixture(name="stream_id")
def f_stream_id():
    return "some_stream"


@pytest.fixture(name="some_data")
def f_some_data():
    return b"some data"


@pytest.fixture(name="monitoring_server_with_subscription")
def f_monitoring_server_with_subscription(monitoring_server, ipv4_address, stream_id, udp_port):
    monitoring_server.connect(ipv4_address, udp_port)
    monitoring_server.subscribe_to_stream(ipv4_address, stream_id)
    return monitoring_server


class TestServer:
    @staticmethod
    def test_connect(monitoring_server, ipv4_address, udp_port):
        monitoring_server.connect(ipv4_address, udp_port)

    @staticmethod
    def test_subscribe_to_stream(monitoring_server, ipv4_address, stream_id):
        monitoring_server.subscribe_to_stream(ipv4_address, stream_id)

    @staticmethod
    def test_dispatch_to_monitors_dispachecs_to_address_after_subscribe(
        monitoring_server_with_subscription, address, stream_id, some_data, mock_socket
    ):

        monitoring_server_with_subscription.dispatch_to_monitors(stream_id, some_data)

        mock_socket.sendto.assert_called_once_with(some_data, address)

    @staticmethod
    def test_dispatch_to_monitors_does_not_dispach_to_address_after_unsubscribe(
        monitoring_server_with_subscription, ipv4_address, stream_id, some_data, mock_socket
    ):
        monitoring_server_with_subscription.unsubscribe_from_stream(ipv4_address, stream_id)

        monitoring_server_with_subscription.dispatch_to_monitors(stream_id, some_data)

        mock_socket.sendto.assert_not_called()

    @staticmethod
    def test_subscription_is_purged(
        monitoring_server_with_subscription, stream_id, some_data, mock_socket, clock
    ):
        clock.time += 4

        monitoring_server_with_subscription.purge_subscriptions()

        monitoring_server_with_subscription.dispatch_to_monitors(stream_id, some_data)
        mock_socket.sendto.assert_not_called()

    @staticmethod
    def test_subscription_is_not_purged(
        monitoring_server_with_subscription,
        address,
        stream_id,
        some_data,
        mock_socket,
        clock,
        ipv4_address,
    ):
        clock.time += 4
        monitoring_server_with_subscription.message_from(ipv4_address)

        monitoring_server_with_subscription.purge_subscriptions()

        monitoring_server_with_subscription.dispatch_to_monitors(stream_id, some_data)
        mock_socket.sendto.assert_called_once_with(some_data, address)


@pytest.fixture(name="dispatch_protocol")
def dispatch_protocol(monitoring_server):
    return monitoring.DispachProtocol(monitoring_server)


class TestDispachProtocol:
    @staticmethod
    @pytest.mark.parametrize(
        "monitoring_server", [mock.MagicMock(spec=monitoring.Server)]
    )
    def test_datagram_received_with_valid_package(
        package,
        dispatch_protocol,
        raw_package,
        monitoring_server,
    ):
        dispatch_protocol.datagram_received(raw_package, mock.MagicMock)

        monitoring_server.dispatch_to_monitors.assert_called_once_with(
            package.stream_id, package.data
        )

