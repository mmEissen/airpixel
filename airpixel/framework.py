import atexit
import asyncio
import dataclasses
import json
import logging
import socket
import subprocess
import time
import typing as t


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

BYTEORDER = "big"


def load_config(file_name):
    with open(file_name) as file_:
        return json.load(file_)


class KeepaliveProtocol(asyncio.DatagramProtocol):
    def __init__(self, process_registration):
        super().__init__()
        self._process_registration = process_registration

    def datagram_received(self, data, addr):
        ip_address, _ = addr
        frames, rendered = (int(n) for n in str(data, "utf-8").split())
        if frames:
            log.info(
                "%s: Received: %s Shown: %s Ratio: %s",
                ip_address,
                frames,
                rendered,
                rendered / frames,
            )
        self._process_registration.response_from(ip_address)


def _subprocess_factory(command):
    return subprocess.Popen("exec " + command, text=True, shell=True)


@dataclasses.dataclass
class ProcessMeta:
    process: t.Any
    ip_address: str
    device_id: str
    last_response: float


class ProcessRegistration:
    def __init__(self, config, subprocess_factory=_subprocess_factory, timeout=3):
        self._config = config
        self._subprocess_factory = subprocess_factory
        self._timeout = timeout
        self._processes = {}
        atexit.register(self.cleanup)

    def kill_process(self, ip_address):
        if ip_address not in self._processes:
            return
        self._processes[ip_address].process.kill()
        self._processes[ip_address].process.communicate()
        del self._processes[ip_address]

    def response_from(self, ip_address):
        try:
            self._processes[ip_address].last_response = time.time()
        except KeyError:
            pass

    def purge_processes(self):
        now = time.time()
        dead_processes = {
            ip
            for ip, process in self._processes.items()
            if now - process.last_response >= self._timeout
        }
        for ip_address in dead_processes:
            log.info("Killing process for %s.", ip_address)
            self.kill_process(ip_address)

    async def purge_forever(self):
        while True:
            self.purge_processes()
            await asyncio.sleep(self._timeout / 4)

    def launch_for(self, device_id, ip_address, streaming_port):
        try:
            base_command = self._config[device_id]
        except KeyError:
            log.warning("No process configured for device ID %s", device_id)
            return None
        try:
            base_command = base_command.format(
                ip_address=ip_address, port=str(streaming_port)
            )
        except KeyError:
            log.warning(
                "Invalid format string for subprocess command for device %s", device_id
            )
            return None
        log.info("Launching process for device %s: `%s`", device_id, base_command)
        self.kill_process(ip_address)
        self._processes[ip_address] = ProcessMeta(
            self._subprocess_factory(base_command), ip_address, device_id, time.time()
        )

    def cleanup(self):
        for process_meta in self._processes.values():
            process_meta.process.kill()


class ConnectionProtocol(asyncio.Protocol):
    PORT_SIZE = 2
    SEPPERATOR = b"\n"

    def __init__(self, process_registration, response_port):
        super().__init__()
        self._process_registration = process_registration
        self.transport = None
        self._current_package = b""
        self.response_port = response_port

    def connection_made(self, transport):
        log.info("New connection")
        self.transport = transport
        self.transport.write(
            int.to_bytes(self.response_port, self.PORT_SIZE, BYTEORDER)
        )

    def register_device(self, registration_bytes):
        port = int.from_bytes(registration_bytes[: self.PORT_SIZE], BYTEORDER)
        device_id = str(registration_bytes[self.PORT_SIZE :], "utf-8")
        ip_address, _ = self.transport.get_extra_info("peername")
        self._process_registration.launch_for(device_id, ip_address, port)

    def data_received(self, data):
        *packages, self._current_package = (self._current_package + data).split(
            self.SEPPERATOR
        )
        if not packages:
            return
        log.info("Received %r", packages)
        self.register_device(packages[0])
        self.transport.close()


async def main():
    config = load_config("airpixel.json")

    log.info(config)

    loop = asyncio.get_running_loop()
    process_registration = ProcessRegistration(config["devices"])
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: KeepaliveProtocol(process_registration),
        local_addr=(config["address"], config["udp_port"]),
        family=socket.AF_INET,
    )

    server = await loop.create_server(
        lambda: ConnectionProtocol(process_registration, config["udp_port"]),
        config["address"],
        config["port"],
    )

    async with server:
        await asyncio.gather(
            server.serve_forever(), process_registration.purge_forever()
        )


if __name__ == "__main__":
    asyncio.run(main())
