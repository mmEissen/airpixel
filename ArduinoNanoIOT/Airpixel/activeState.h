#pragma once

#include "state.h"
#include "constants.h"

class ActiveState : public State {
    public:
        ActiveState(GlobalState & globalState) 
            : State(globalState)
        {}
        State* checkTransition() override;
        void performAction() override;

        #if DEBUG_MODE
        const char * name() override { return "Active State"; }
        #endif
};
