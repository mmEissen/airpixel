#pragma once

#include "state.h"
#include "constants.h"

#include <WiFiUdp.h>
#include <NeoPixelBus.h>

class ActiveState : public State {
    public:
        ActiveState(GlobalState & globalState) : State(globalState), _udp(), _pixels(PIXEL_COUNT, LED_PIN) {
            _udp.begin(LOCAL_UDP_PORT);
        }
        State* checkTransition() override;
        void performAction() override;

        #if DEBUG_MODE
        const char * name() override { return "Active State"; }
        #endif

    private:
        WiFiUDP _udp;
        NeoPixelBus<Neo3Elements, Neo800KbpsMethod> _pixels;
};
