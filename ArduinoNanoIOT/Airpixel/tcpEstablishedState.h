#pragma once

#include "state.h"

#include <WiFiNINA.h>

class TcpEstablishedState : public State {
    public:
        using State::State;
        State * checkTransition() override;
        void performAction() override;

        #if DEBUG_MODE
        const char * name() override { return "TCP Established State"; }
        #endif
};
