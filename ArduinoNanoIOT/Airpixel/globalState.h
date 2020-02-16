#pragma once

#include "constants.h"

#include <SPI.h>
#include <WiFiNINA.h>
#include <WiFiUdp.h>
#include <NeoPixelBus.h>

class State;

class GlobalState {
    public:
        GlobalState()
            : _tcpClient()
            , _udp()
            , _pixels(PIXEL_COUNT, LED_PIN)
        {}

        void begin() {
            _pixels.Begin();
            _udp.begin(LOCAL_UDP_PORT);
        }

        State* nextState();

        WiFiClient & tcpClient() { return _tcpClient; }
        NeoPixelBus<Neo3Elements, NeoArm800KbpsMethod> & pixels() { return _pixels; }
        WiFiUDP & udp() { return _udp; }
    protected:
        WiFiClient _tcpClient;
        NeoPixelBus<Neo3Elements, NeoArm800KbpsMethod> _pixels;
        WiFiUDP _udp;
};
