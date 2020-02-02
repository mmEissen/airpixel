#include "state.h"

class DisconnectedState : public State {
    public:
        using State::State;
        State* checkTransition() override;
        void performAction() override;
};
