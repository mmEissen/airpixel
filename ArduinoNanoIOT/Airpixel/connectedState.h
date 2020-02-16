#pragma once

#include "state.h"

class ConnectedState : public State {
    public:
        using State::State;
        State* checkTransition() override;
        void performAction() override;

        const char * name() override { return "Connected State"; }
};
