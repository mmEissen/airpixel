from __future__ import annotations

import asyncio
import socket
import sys
import time
import typing as t
import numpy
import dataclasses
import io
import threading

import yaml

from pyqtgraph.Qt import QtGui
import pyqtgraph as pg
from PyQt5 import QtCore
import numpy as np

from airpixel import monitoring


class PlotProtocol(asyncio.DatagramProtocol):
    def __init__(self, plots):
        self.plots = plots

    def datagram_received(self, data: bytes, addr: t.Tuple[str, int]) -> None:
        package = monitoring.Package.from_bytes(data)

        if package.stream_id not in self.plots: 
            return

        memfile = io.BytesIO()
        memfile.write(package.data)
        memfile.seek(0)
        array = numpy.load(memfile)
        
        self.plots[package.stream_id].new_data.emit(array)


class MonitorServer:
    def __init__(self, ip_address, port, plots):
        self.ip_address = ip_address
        self.port = port
        self.plots = plots
        self.local_port = 0
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(0)

    async def run_forever(self):
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: PlotProtocol(self.plots), local_addr=("0.0.0.0", 0), family=socket.AF_INET,
        )
        _, self.local_port = transport.get_extra_info("sockname")

        keepalive_port = self.connect()

        for stream_id in self.plots:
            self.subscribe(stream_id)

        while True:
            self.socket.sendto(b"", (self.ip_address, keepalive_port))
            await asyncio.sleep(1)

    def subscribe(self, stream_id):
        with socket.create_connection((self.ip_address, int(self.port))) as sock:
            sock.send(
                monitoring.Command(
                    monitoring.CommandVerb.SUBSCRIBE, bytes(stream_id, "utf-8")
                ).to_bytes()
            )

    def connect(self):
        with socket.create_connection((self.ip_address, int(self.port))) as sock:
            sock.send(
                monitoring.Command(
                    monitoring.CommandVerb.CONNECT,
                    bytes(f"{self.local_port}", "utf-8"),
                ).to_bytes()
            )
            response_data = sock.recv(128)
        response = monitoring.CommandResponse.from_bytes(response_data)
        return int(response.info)

    def run(self):
        asyncio.run(self.run_forever())


@dataclasses.dataclass
class StreamConfig:
    name: str

    @classmethod
    def from_dict(cls, dict_: t.Dict[str, t.Any]) -> StreamConfig:
        return cls(dict_["name"])


@dataclasses.dataclass
class Config:
    server: str
    port: int
    streams: t.List[StreamConfig]

    @classmethod
    def from_dict(cls, dict_: t.Dict[str, t.Any]) -> Config:
        return cls(
            dict_["server"],
            dict_["port"],
            [StreamConfig.from_dict(dict_) for dict_ in dict_["streams"]],
        )

    @classmethod
    def load(cls, file_name: str) -> Config:
        with open(file_name) as file_:
            return cls.from_dict(yaml.safe_load(file_)["monitor"])


class SimplePlot(pg.PlotWidget):
    new_data = QtCore.pyqtSignal(np.ndarray)

    def __init__(self, stream_id: str):
        super().__init__(title=stream_id)
        self.stream_id = stream_id
        self._current_max_y = 0
        self._curve = self.plot(pen="y")

    def _fit_plot(self, points):
        self._current_max_y = max(max(points), self._current_max_y)
        self.setRange(yRange=(0, self._current_max_y))

    def plot_array(self, data):
        self._curve.setData(data)
        self._fit_plot(data)


class Application:
    def __init__(self, config: Config, q_app):
        self.config = config
        self.plots = {}
        self.server = MonitorServer(self.config.server, self.config.port, self.plots)

        self.q_app = q_app
        self.top_widget = QtGui.QWidget()
        self.top_widget.resize(1800, 900)

        self.layout = QtGui.QGridLayout()
        self.top_widget.setLayout(self.layout)
        for i, stream in enumerate(self.config.streams):
            self.plots[stream.name] = SimplePlot(stream.name)
            self.plots[stream.name].new_data.connect(self.plots[stream.name].plot_array)
            self.layout.addWidget(self.plots[stream.name], i, 0)

    def run_forever(self) -> None:
        server_thread = threading.Thread(target=self.server.run, daemon=True)
        server_thread.start()

        self.top_widget.show()

        self.q_app.exec_()


def main() -> None:
    config = Config.load("monitor.yaml")

    q_app = QtGui.QApplication([])
    app = Application(config, q_app)
    try:
        app.run_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
