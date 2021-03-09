import io
import os
import time

import numpy as np  # type: ignore

from airpixel import client

mon_client = client.MonitorClient(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "monitoring_uds")
)

while True:
    arr = np.random.random(1000)
    file_ = io.BytesIO()
    np.save(file_, arr, False)
    mon_client.send_data("random", file_.getvalue())
    time.sleep(0.01)
