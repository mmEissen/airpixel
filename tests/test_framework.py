import asyncio
import subprocess
from unittest import mock

import pytest

from airpixel import framework


@pytest.fixture(name="device_ip_address")
def f_device_ip_address():
    return "1.2.3.4"


@pytest.fixture(name="device_udp_port")
def f_device_udp_port():
    return 60000


@pytest.fixture(name="tcp_port")
def f_tcp_port():
    return 50000


@pytest.fixture(name="device_name")
def f_device_name():
    return "some_device"


@pytest.fixture(name="sh_command_template")
def f_sh_command_template():
    return "some command {ip_address} {port}"


@pytest.fixture(name="registration_timeout")
def f_registration_timeout():
    return 5


@pytest.fixture(name="device_config")
def f_device_config(device_name, sh_command_template):
    return framework.DeviceConfig(device_name, sh_command_template)


@pytest.fixture(name="device_configs")
def f_device_configs(device_config):
    return [device_config]


@pytest.fixture(name="mock_subprocess")
def f_mock_subprocess():
    return mock.MagicMock(spec=subprocess.Popen)


@pytest.fixture(name="subprocess_factory")
def f_subprocess_factory(mock_subprocess):
    return mock.MagicMock(return_value=mock_subprocess)


@pytest.fixture(name="connected_connection_protocol")
def f_connected_connection_protocol(connection_protocol, mock_transport):
    connection_protocol.connection_made(mock_transport)
    return connection_protocol


@pytest.fixture(name="device_registration_data")
def f_device_registration_data(device_name, device_udp_port):
    return (
        int.to_bytes(
            device_udp_port, framework.ConnectionProtocol.PORT_SIZE, framework.BYTEORDER
        )
        + bytes(device_name, "utf-8")
        + framework.ConnectionProtocol.SEPPERATOR
    )


@pytest.fixture(name="process_registration")
def f_process_registration(device_configs, subprocess_factory, registration_timeout):
    return framework.ProcessRegistration(
        device_configs,
        subprocess_factory=subprocess_factory,
        timeout=registration_timeout,
    )


@pytest.fixture(name="mock_process_registration")
def f_mock_process_registration():
    return mock.MagicMock(spec=framework.ProcessRegistration)


@pytest.fixture(name="recieved_frames_number")
def f_recieved_frames_number():
    return 10


@pytest.fixture(name="drawn_frames_number")
def f_drawn_frames_number():
    return 11


@pytest.fixture(name="device_keepalive_data")
def f_device_keepalive_data(recieved_frames_number, drawn_frames_number):
    return bytes(f"{recieved_frames_number} {drawn_frames_number}", "utf-8")


@pytest.fixture(name="keepalive_protocol")
def f_keepalive_protocol(mock_process_registration):
    return framework.KeepaliveProtocol(mock_process_registration)


@pytest.fixture(name="mock_transport")
def f_mock_transport():
    return mock.AsyncMock(spec=asyncio.Transport)


@pytest.fixture(name="connection_protocol")
def f_connection_protocol(mock_process_registration, udp_port):
    return framework.ConnectionProtocol(mock_process_registration, udp_port)


class TestProcessRegistration:
    @staticmethod
    def test_launch_for_launches_process(
        process_registration,
        device_name,
        subprocess_factory,
        device_ip_address,
        device_udp_port,
        sh_command_template,
    ):
        process_registration.launch_for(device_name, device_ip_address, device_udp_port)

        subprocess_factory.assert_called_once_with(
            sh_command_template.format(
                ip_address=device_ip_address, port=device_udp_port
            )
        )

    @staticmethod
    def test_launch_for_kills_previously_launched_process(
        process_registration,
        device_name,
        mock_subprocess,
        device_ip_address,
        device_udp_port,
    ):
        process_registration.launch_for(device_name, device_ip_address, device_udp_port)

        process_registration.launch_for(device_name, device_ip_address, device_udp_port)

        mock_subprocess.kill.assert_called_once()
        mock_subprocess.communicate.assert_called_once()

    @staticmethod
    def test_purge_processes_kills_old_processes(
        process_registration,
        device_name,
        device_ip_address,
        device_udp_port,
        mock_subprocess,
        clock,
        registration_timeout,
    ):
        process_registration.launch_for(device_name, device_ip_address, device_udp_port)
        clock.time += registration_timeout + 1

        process_registration.purge_processes()

        mock_subprocess.kill.assert_called_once()
        mock_subprocess.communicate.assert_called_once()

    @staticmethod
    def test_purge_processes_does_not_kill_recently_active(
        process_registration,
        device_name,
        device_ip_address,
        device_udp_port,
        mock_subprocess,
        clock,
        registration_timeout,
    ):
        process_registration.launch_for(device_name, device_ip_address, device_udp_port)
        clock.time += registration_timeout + 1
        process_registration.response_from(device_ip_address)
        clock.time += registration_timeout / 2

        process_registration.purge_processes()

        mock_subprocess.kill.assert_not_called()

    @staticmethod
    def test_purge_processes_does_not_kill_recently_created(
        process_registration,
        device_name,
        device_ip_address,
        device_udp_port,
        mock_subprocess,
        clock,
        registration_timeout,
    ):
        process_registration.launch_for(device_name, device_ip_address, device_udp_port)
        clock.time += registration_timeout / 2

        process_registration.purge_processes()

        mock_subprocess.kill.assert_not_called()


class TestKeepaliveProtocol:
    @staticmethod
    def test_datagram_received(
        device_keepalive_data,
        keepalive_protocol,
        device_udp_port,
        device_ip_address,
        mock_process_registration,
    ):
        keepalive_protocol.datagram_received(
            device_keepalive_data, (device_ip_address, device_udp_port)
        )

        mock_process_registration.response_from.assert_called_once_with(
            device_ip_address
        )


class TestConnectionProtocol:
    @staticmethod
    def test_connection_made(connection_protocol, mock_transport, udp_port):
        connection_protocol.connection_made(mock_transport)

        assert connection_protocol.transport is mock_transport

    @staticmethod
    @pytest.mark.parametrize("process_registration", [mock.MagicMock()])
    def test_data_received_with_no_separator_does_nothing(
        connection_protocol, mock_transport, udp_port, process_registration
    ):
        connection_protocol.data_received(b"noseparator")

        mock_transport.close.assert_not_called()
        process_registration.launch_for.assert_not_called()

    @staticmethod
    def test_data_received_launches_process_and_closes_connection(
        connected_connection_protocol,
        mock_transport,
        mock_process_registration,
        device_ip_address,
        device_udp_port,
        udp_port,
        device_name,
        device_registration_data,
    ):
        mock_transport.get_extra_info.return_value = (
            device_ip_address,
            device_udp_port,
        )

        connected_connection_protocol.data_received(device_registration_data)

        mock_transport.close.assert_called_once()
        mock_process_registration.launch_for.assert_called_once_with(
            device_name, device_ip_address, device_udp_port
        )
        mock_transport.write.assert_called_once_with(
            int.to_bytes(
                udp_port, framework.ConnectionProtocol.PORT_SIZE, framework.BYTEORDER
            )
        )

    @staticmethod
    def test_data_received_launches_process_and_closes_connection_if_message_was_split(
        connected_connection_protocol,
        mock_transport,
        mock_process_registration,
        device_ip_address,
        device_udp_port,
        device_name,
        device_registration_data,
    ):
        mock_transport.get_extra_info.return_value = (
            device_ip_address,
            device_udp_port,
        )
        part1 = device_registration_data[:2]
        part2 = device_registration_data[2:]
        connected_connection_protocol.data_received(part1)

        connected_connection_protocol.data_received(part2)

        mock_transport.close.assert_called_once()
        mock_process_registration.launch_for.assert_called_once_with(
            device_name, device_ip_address, device_udp_port
        )
