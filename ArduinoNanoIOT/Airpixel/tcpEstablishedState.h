#pragma once

#include "state.h"

#include <WiFiNINA.h>

class TcpEstablishedState : public State {
    public:
        using State::State;
        State * checkTransition() override;
        void performAction() override;

        const char * name() override { return "TCP Established State"; }
        virtual const uint8_t statusLed() override { return 2; }
};
