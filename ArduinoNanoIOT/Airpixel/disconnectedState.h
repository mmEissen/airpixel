#pragma once

#include "state.h"
#include "constants.h"

class DisconnectedState : public State {
    public:
        using State::State;
        State* checkTransition() override;
        void performAction() override;

        #if DEBUG_MODE
        const char * name() override { return "Disconnected State"; }
        #endif
};
