#include "activeState.h"

#include <string>

#include <SPI.h>
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
        digitalWrite(STATUS_1_PIN, true);
        _lastResponse = millis();
        _globalState.udp().beginPacket(SERVER_TCP_IP, _globalState.responsePort());
        _globalState.udp().write(std::to_string(_receivedFrames).c_str());
        _globalState.udp().write(" ");
        _globalState.udp().write(std::to_string(_shownFrames).c_str());
        _globalState.udp().endPacket();
        digitalWrite(STATUS_1_PIN, false);
    }

    bool available = false;
    while (true) {
        auto chars_available = _globalState.udp().parsePacket();
        if (!chars_available) {
            break;
        }
        ++_receivedFrames;
        uint64_t frameNumber = 0;
        for (int i = 0; i < CHARS_IN_UINT64 ; ++i) {
            frameNumber = frameNumber << 8;
            auto c = _globalState.udp().read();
            frameNumber += c;
        }
        if (frameNumber > _highestFrameNumber) {
            digitalWrite(STATUS_2_PIN, true);
            _globalState.udp().read(_globalState.pixels().Pixels(), chars_available - CHARS_IN_UINT64);
            _globalState.pixels().Dirty();
            _highestFrameNumber = frameNumber;
            available = true;
            digitalWrite(STATUS_2_PIN, false);
        }
    }
    if (available) {
        digitalWrite(STATUS_1_PIN, true);
        digitalWrite(STATUS_2_PIN, true);
        ++_shownFrames;
        _lastMessage = millis();
        _globalState.pixels().Show();
        DEBUG((uint32_t) _highestFrameNumber % 0xFFFFFFFF);
        digitalWrite(STATUS_1_PIN, false);
        digitalWrite(STATUS_2_PIN, false);
    }
}
