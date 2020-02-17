#include "activeState.h"

#include <WiFiNINA.h>

#include "constants.h"


State* ActiveState::checkTransition() {
    return this;
}

void ActiveState::performAction() {
    bool available = false;
    while (true) {
        auto chars_available = _globalState.udp().parsePacket();
        DEBUG("available");
        DEBUG(chars_available);
        if (!chars_available) {
            break;
        }
        uint64_t frameNumber = 0;
        for (int i = 0; i < CHARS_IN_UINT64 ; ++i) {
            frameNumber << 8;
            auto c = _globalState.udp().read();
            frameNumber += c;
        }
        DEBUG((uint32_t) frameNumber % 0xFFFFFFFF);
        if (frameNumber > highestFrameNumber) {
            _globalState.udp().read(_globalState.pixels().Pixels(), chars_available - CHARS_IN_UINT64);
            _globalState.pixels().Dirty();
            available = true;
            highestFrameNumber = frameNumber;
        }
    }
    if (available) {
        DEBUG("render frame");
        DEBUG((uint32_t) highestFrameNumber % 0xFFFFFFFF);
        _globalState.pixels().Show();
    }
}
