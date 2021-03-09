import socket
import sys
import time


def main() -> None:
    name = sys.argv[1]

    with socket.create_connection(("0.0.0.0", 50000)) as sock:
        sock.send(int.to_bytes(54325, 2, "big") + bytes(name, "utf-8") + b"\n")
        port_bytes = sock.recv(8)
        port = int.from_bytes(port_bytes, byteorder="big")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0)
    while True:
        time.sleep(2)
        sock.sendto(b"1 1", ("0.0.0.0", port))


if __name__ == "__main__":
    main()
