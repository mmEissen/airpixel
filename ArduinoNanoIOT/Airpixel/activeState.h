#pragma once

#include "state.h"
#include "constants.h"

class ActiveState : public State {
    public:
        ActiveState(GlobalState & globalState) 
            : State(globalState)
            , _highestFrameNumber(0)
            , _lastMessage(0)
            , _lastResponse(0)
            , _receivedFrames(0)
            , _shownFrames(0)
        {}
        State* checkTransition() override;
        void performAction() override;

        const char * name() override { return "Active State"; }
        virtual const uint8_t statusLed() override { return 0; }
    private:
        uint64_t _highestFrameNumber;
        unsigned long _lastMessage;
        unsigned long _lastResponse;
        unsigned long _receivedFrames;
        unsigned long _shownFrames;
};
