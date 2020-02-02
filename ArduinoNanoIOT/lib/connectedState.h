#include "state.h"

class ConnectedState : public State {
    public:
        using State::State;
        State* checkTransition() override;
        void performAction() override;
};
