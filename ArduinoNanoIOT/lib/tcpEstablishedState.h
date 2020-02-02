#include "state.h"

class TcpEstablishedState : public State {
    public:
        using State::State;
        State* checkTransition() override;
        void performAction() override;
};
