from unittest import mock

import pytest

from airpixel import framework


@pytest.fixture(name="process_transport")
def process_transport_fixture():
    return mock.MagicMock()


@pytest.fixture(name="process_factory")
def process_factory_fixture(process_transport):
    def _factory(protocol, *args):
        return mock.MagicMock(return_value=(process_transport, mock.MagicMock()))
    return _factory


@pytest.fixture(name="device_configuration")
def device_configuration_fixture(process_factory):
    return framework.DeviceConfiguration({}, subprocess_factory=process_factory)


@pytest.fixture(name="mock_device_configuration")
def mock_device_configuration_fixture(process_factory):
    return mock.MagicMock()


@pytest.fixture(name="supervisor_protocol")
def supervisor_protocol_fixture(mock_device_configuration):
    return framework.SupervisorProtocol(mock_device_configuration)


class TestSupervisorProtocol:
    @staticmethod
    def test_data_received(process_transport, mock_device_configuration, supervisor_protocol):

        supervisor_protocol.data_received(b"123456781234\n")

        mock_device_configuration.launch_from_config.assert_called_once_with(
            b"12345678",
            b"1234",
            supervisor_protocol.close,
        )
        process_transport.close.assert_not_called()

    @staticmethod
    @pytest.mark.parametrize(
        "message",
        [
            b"message\n",
            b"\n",
            b"12345678901234567890\n"
        ]
    )
    def test_data_received_doesnt_raise(supervisor_protocol, message):
        mock_transport = mock.MagicMock()
        supervisor_protocol.transport = mock_transport

        supervisor_protocol.data_received(message)

        mock_transport.close.assert_called_once()


class TestDeviceConfiguration:
    pass
