#include "activeState.h"

#include <WiFiNINA.h>

#include "constants.h"


State* ActiveState::checkTransition() {
    return this;
}

void ActiveState::performAction() {
    int available = 0;
    uint64_t highestFrameNumber = 0;
    while (available = _globalState.udp().parsePacket()) {
        uint64_t frameNumber = 0;
        for (int i = 0; i < CHARS_IN_UINT64 ; ++i) {
            frameNumber << sizeof(char);
            frameNumber += _globalState.udp().read();
        }
        if (frameNumber > highestFrameNumber) {
            _globalState.udp().read(_globalState.pixels().Pixels(), available - CHARS_IN_UINT64);
            _globalState.pixels().Dirty();
        }
    }
    if (available) {
        _globalState.pixels().Show();
    }
}
