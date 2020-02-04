#pragma once

#include <WiFiNINA.h>

class State;

class GlobalState {
    public:
        GlobalState() : _tcpClient() {}

        State* nextState();

        WiFiClient & tcpClient() { return _tcpClient; }
    protected:
        WiFiClient _tcpClient;
};
