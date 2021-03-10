# Airpixel

A software framework to remote control NeoPixel or similar LEDs

## Why?

There are two main applications for this:

1. You wish to rapidly prototype your designs for applications using coloured LEDs. In this case compiling and uploading code to a microcontroler can take up a significant part of your time and patience.
2. Your application requires significant processing power and you need to offload computation to another device.

In both cases this framework can help you.

## Usage

### Hardware Requirements

You will need an [ArduinoNANO 33 IOT](https://store.arduino.cc/arduino-nano-33-iot), and some [NeoPixel LEDs](https://www.adafruit.com/category/168). Other off-brand LED products will most likely also work. Please follow one of Adafruits guides to connect your NeoPixels to your Arduino.
I recommend to connect the NeoPixels to this frameworks default PIN 2. This will save you some configuration later.

### Software Requirements

You will need [Docker](https://www.docker.com/) and [Python 3.7+](https://www.python.org/).

### Setup

Connect your Arduino via USB to your computer and run
```
docker run --privileged mmeissen/upload-airpixel-arduino-nano-iot
```

TODO: explain configuration options

To install the server run:
```
pip install airpixel
```

To run the server run:
```
python -m airpixel
```

TODO: Explain configuation of the server
