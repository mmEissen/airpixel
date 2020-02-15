import subprocess
import asyncio
import logging
import json
import socket

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def load_config(file_name):
    with open(file_name) as file_:
        return json.load(file_)


class DeviceProcessProtocol(asyncio.SubprocessProtocol):
    def __init__(self, on_exit):
        super().__init__()
        self._on_exit = on_exit

    def process_exited(self):
        self._on_exit()


def _subprocess_factory(protocol, *args):
    loop = asyncio.get_running_loop()
    loop.subprocess_exec(protocol, *args)


class DeviceConfiguration:
    def __init__(self, config, subprocess_factory=_subprocess_factory):
        self._config = config
        self._subprocess_factory = subprocess_factory

    def launch_from_config(self, device_id, streaming_port, exit_callback=lambda: None):
        try:
            base_command = self._config[device_id]
        except KeyError:
            log.warning("No process configured for device ID %s", device_id)
            return
        try:
            base_command = base_command.format(port=str(streaming_port, "utf-8"))
        except KeyError:
            log.warning(
                "Invalid format string for subprocess command for device %s", device_id
            )
            return
        command = base_command.split()
        transport, _ = self._subprocess_factory(
            lambda: DeviceProcessProtocol(on_exit=exit_callback), command
        )
        return transport


class SupervisorProtocol(asyncio.Protocol):
    PORT_SIZE = 4
    REGISTER_BYTES = PORT_SIZE + DEVICE_ID_SIZE
    SEPPERATOR = b"\n"

    def __init__(self, device_configuration):
        super().__init__()
        self._device_configuration = device_configuration
        self.transport = None
        self._subprocess = None
        self._current_package = b""

    def connection_made(self, transport):
        log.info("New connection")
        self.transport = transport
        sock = self.transport.get_extra_info('socket')
        TCP_KEEPALIVE = 0x10
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)

    def register_device(self, registration_bytes):
        if len(registration_bytes) != self.REGISTER_BYTES:
            return None
        port = registration_bytes[ : self.PORT_SIZE]
        device_id = registration_bytes[self.PORT_SIZE :]
        return self._device_configuration.launch_from_config(
            device_id, port, self.close
        )

    def close(self):
        if self.transport is not None:
            self.transport.close()

    def data_received(self, data):
        *packages, self._current_package = (self._current_package + data).split(
            self.SEPPERATOR
        )
        if not packages:
            return
        log.info("Received %r", packages)
        self._subprocess = self._subprocess or self.register_device(packages[0])
        if self._subprocess is None:
            self.transport.close()

    def connection_lost(self, exc):
        if self._subprocess is not None:
            self._subprocess.close()
        if exc is not None:
            log.warn("Connection lost %r", exc)
        else:
            log.info("Connection closed")


async def main():
    config = load_config("airpixel.json")

    log.info(config)

    loop = asyncio.get_running_loop()
    device_config = DeviceConfiguration(config["devices"])
    server = await loop.create_server(
        lambda: SupervisorProtocol(device_config), config["address"], config["port"]
    )

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
