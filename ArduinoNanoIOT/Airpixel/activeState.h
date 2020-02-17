#pragma once

#include "state.h"
#include "constants.h"

class ActiveState : public State {
    public:
        ActiveState(GlobalState & globalState) 
            : State(globalState)
            , highestFrameNumber(0)
        {}
        State* checkTransition() override;
        void performAction() override;

        const char * name() override { return "Active State"; }
    private:
        uint64_t highestFrameNumber;
};
