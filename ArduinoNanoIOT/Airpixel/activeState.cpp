#include "activeState.h"

#include <WiFiNINA.h>

#include "constants.h"
#include "connectedState.h"


State* ActiveState::checkTransition() {
    if (_lastMessage == 0) {
        _lastMessage = millis();
    }
    if (millis() - _lastMessage > TIMEOUT) {
        return new ConnectedState(_globalState);
    }
    return this;
}

void ActiveState::performAction() {
    if (millis() - _lastResponse > HEARTBEAT_DELTA) {
        _lastResponse = millis();
        _globalState.udp().beginPacket(SERVER_TCP_IP, _globalState.responsePort());
        _globalState.udp().write("ping");
        _globalState.udp().endPacket();
    }

    bool available = false;
    while (true) {
        auto chars_available = _globalState.udp().parsePacket();
        if (!chars_available) {
            break;
        }
        uint64_t frameNumber = 0;
        for (int i = 0; i < CHARS_IN_UINT64 ; ++i) {
            frameNumber = frameNumber << 8;
            auto c = _globalState.udp().read();
            frameNumber += c;
        }
        if (frameNumber > _highestFrameNumber) {
            _globalState.udp().read(_globalState.pixels().Pixels(), chars_available - CHARS_IN_UINT64);
            _globalState.pixels().Dirty();
            available = true;
            _highestFrameNumber = frameNumber;
        }
    }
    if (available) {
        _lastMessage = millis();
        _globalState.pixels().Show();
        DEBUG((uint32_t) _highestFrameNumber % 0xFFFFFFFF);
    }
}
