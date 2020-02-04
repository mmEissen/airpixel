#pragma once

#include "globalState.h"
#include "constants.h"

class State {
    public:
        State(GlobalState & globalState) : _globalState(globalState) {}
        virtual State* checkTransition() { return this; }
        virtual void performAction() = 0;
        virtual void onEnter() {};
        virtual void onExit() {};

        #if DEBUG_MODE
        virtual const char * name() { return "Some State"; };
        #endif
    protected:
        GlobalState & _globalState;
};
