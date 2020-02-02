#include "globalState.h"

class State {
    public:
        State(GlobalState & globalState) : _globalState(globalState) {}
        virtual State* checkTransition() { return this; }
        virtual void performAction() = 0;
        virtual void onEnter() {};
        virtual void onExit() {};
    protected:
        GlobalState & _globalState;
};
