import sys
import time
from airpixel import client

ip, port = sys.argv[1:3]
print("Starting blink: ", ip, int(port))

c = client.AirClient(ip, int(port))
on = client.Pixel(0.5, 0, 0)
off = client.Pixel(0, 0, 0)
delta_t = 0.02

while True:
    if time.time() % 0.2 < 0.1:
        c.show_frame([on] * 4)
    else:
        c.show_frame([off] * 4)
    time.sleep(delta_t)
