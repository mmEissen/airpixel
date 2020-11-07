FROM python:3.8

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install click==7.1.2

RUN curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

RUN arduino-cli core update-index && arduino-cli core install arduino:samd@1.8.9

RUN arduino-cli lib update-index && arduino-cli lib install \
    "NeoPixelBus by Makuna@2.6.0" \
    Sodaq_wdt@1.0.2 \
    WiFiNINA@1.7.1 \
    ;

RUN mkdir /ArduinoNanoIOT
COPY Airpixel /root/Arduino/libraries/Airpixel
COPY ArduinoNanoIOT.ino /ArduinoNanoIOT/ArduinoNanoIOT.ino
COPY run.py /ArduinoNanoIOT/run.py

WORKDIR /ArduinoNanoIOT

# arduino-cli compile -b arduino:samd:nano_33_iot
ENTRYPOINT ["bash"]
