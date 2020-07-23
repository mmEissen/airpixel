import subprocess
from unittest import mock

import pytest

from airpixel import framework


@pytest.fixture(name="ipv4_address")
def ipv4_address_():
    return "192.168.2.100"


@pytest.fixture(name="device_ip_address")
def device_ip_address_():
    return "1.2.3.4"


@pytest.fixture(name="device_udp_port")
def device_udp_port_():
    return 60000


@pytest.fixture(name="tcp_port")
def tcp_port_():
    return 50000


@pytest.fixture(name="udp_port")
def udp_port_():
    return 50001


@pytest.fixture(name="device_name")
def device_name_():
    return "some_device"


@pytest.fixture(name="sh_command_template")
def sh_command_template_():
    return "some command {ip_address} {port}"


@pytest.fixture(name="registration_timeout")
def registration_timeout_():
    return 5


@pytest.fixture(name="clock")
def clock_():
    class MockClock:
        def __init__(self):
            self.time = 1_000_000_000

        def __call__(self):
            return self.time

    with mock.patch("time.time", new=MockClock()) as clock:
        yield clock


@pytest.fixture(name="device_config")
def device_config_(device_name, sh_command_template):
    return {device_name: sh_command_template}


@pytest.fixture(name="config")
def config_(ipv4_address, tcp_port, udp_port, device_config):
    return {
        "address": ipv4_address,
        "port": tcp_port,
        "udp_port": udp_port,
        "devices": device_config,
    }


@pytest.fixture(name="mock_subprocess")
def mock_subprocess_():
    return mock.MagicMock(spec=subprocess.Popen)


@pytest.fixture(name="subprocess_factory")
def subprocess_factory_(mock_subprocess):
    return mock.MagicMock(return_value=mock_subprocess)


@pytest.fixture(name="process_registration")
def process_registration_(device_config, subprocess_factory, registration_timeout):
    return framework.ProcessRegistration(
        device_config,
        subprocess_factory=subprocess_factory,
        timeout=registration_timeout,
    )


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