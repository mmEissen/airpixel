import sys
import time
from airpixel import client

ip, port = sys.argv[1:2]

c = client.AirClient()
on = client.Pixel(1, 1, 1)
off = client.Pixel(0, 0, 0)

while True:
    c.show_frame([on] * 4)
    time.sleep(0.1)
    c.show_frame([off] * 4)
    time.sleep(0.1)
