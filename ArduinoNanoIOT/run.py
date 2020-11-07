#!/bin/python
import dataclasses
import json
import subprocess

import click


CONFIG_FILE = "/root/Arduino/libraries/Airpixel/config.h"
ARDUINO_NANO_33_IOT_FQBN = "arduino:samd:nano_33_iot"


class NoDeviceError(Exception):
    pass


def to_bytes(string: str) -> bytes:
    return bytes(string, "utf-8")


@dataclasses.dataclass
class Config:
    device_id: str

    debug_mode: bool = False
    server_ip: str = "192.168.4.1"
    server_port: int = 50000
    wifi_ssid: str = "AIRPIXEL"
    wifi_password: str = "34D6MasF8B2M2ws8"
    led_pin: int = 2
    status_1_pin: int = 3
    status_2_pin: int = 4

    def to_string(self):
        return (
            f"#pragma once\n"
            f'#define DEVICE_ID "{to_bytes(self.device_id)}"\n'
            f"#define DEBUG_MODE {int(self.debug_mode)}\n"
            f'#define SERVER_TCP_IP "{self.server_ip}"\n'
            f"#define SERVER_TCP_PORT {self.server_port}\n"
            f'#define WIFI_SSID "{to_bytes(self.wifi_ssid)}"\n'
            f'#define WIFI_PASSWORD "{to_bytes(self.wifi_password)}"\n'
            f"#define LED_PIN {self.led_pin}\n"
            f"#define STATUS_1_PIN {self.status_1_pin}\n"
            f"#define STATUS_2_PIN {self.status_2_pin}\n"
        )


def write_config(config: Config):
    with open(CONFIG_FILE, "w") as file_:
        file_.write(config.to_string())


def find_device():
    devices = json.loads(
        subprocess.run(
            ["arduino-cli", "--format", "json", "board", "list"],
            capture_output=True,
            check=True,
        ).stdout
    )
    for device in devices:
        try:
            fqbn = device["boards"][0]["FQBN"]
        except (KeyError, IndexError):
            pass
        else:
            if fqbn == ARDUINO_NANO_33_IOT_FQBN:
                return device["address"]
    raise NoDeviceError(
        "Could not find an Arduino NANO 33 IoT. Are you running docker with --privileged flag?"
    )


@click.command()
@click.argument("device_id", required=True)
def main(device_id):
    write_config(Config(device_id))
    device_adress = find_device()
    print(f"Found an Arduino NANO 33 IoT at {device_adress}.")
    print("Compiling...")
    subprocess.run(
        ["arduino-cli", "compile", "--fqbn", ARDUINO_NANO_33_IOT_FQBN], check=True
    )
    print("Uploading...")
    subprocess.run(
        [
            "arduino-cli",
            "upload",
            "--fqbn",
            ARDUINO_NANO_33_IOT_FQBN,
            "--port",
            device_adress,
        ],
        check=True,
    )
    print("Done!")


if __name__ == "__main__":
    main()
