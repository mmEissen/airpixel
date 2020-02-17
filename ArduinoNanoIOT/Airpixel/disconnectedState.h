#pragma once

#include "state.h"
#include "constants.h"

class DisconnectedState : public State {
    public:
        DisconnectedState(GlobalState & globalState) 
            : State(globalState)
            , is_connecting(false)
        {}
        State* checkTransition() override;
        void performAction() override;
        
        const char * name() override { return "Disconnected State"; }
        virtual const uint8_t statusLed() override { return 3; }
    private:
        bool is_connecting;
};
