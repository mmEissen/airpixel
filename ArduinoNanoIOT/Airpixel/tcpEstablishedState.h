#pragma once

#include "state.h"

#include <WiFiNINA.h>

class TcpEstablishedState : public State {
    public:
        TcpEstablishedState(GlobalState & globalState)
            : State(globalState)
            ,_responsePort(0)
            , _charCount(0)
        {}
        State * checkTransition() override;
        void performAction() override;
        void onEnter() override;
        void onExit() override;

        const char * name() override { return "TCP Established State"; }
        virtual const uint8_t statusLed() override { return 2; }
    private:
        uint16_t _responsePort;
        size_t _charCount;
};
