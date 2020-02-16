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

        virtual const char * name() = 0;
    protected:
        GlobalState & _globalState;
};
