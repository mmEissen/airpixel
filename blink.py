import sys
import time
from airpixel import client

ip, port = sys.argv[1:3]
print("Starting blink: ", ip, int(port))

c = client.AutoClient()
c.begin(ip, int(port))
on = client.Pixel(0.5, 0, 0)
off = client.Pixel(0, 0, 0)
delta_t = 0.2

while True:
    c.show_frame([on] * 50)
    time.sleep(delta_t)
    c.show_frame([off] * 50)
    time.sleep(delta_t)
