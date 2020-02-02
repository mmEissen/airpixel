#include <WiFiNINA.h>

#include "constants.h"
#include "connectedState.h"
#include "disconnectedState.h"


State* ConnectedState::checkTransition() {
    if (_globalState.tcpClient().connected()) {
        // return new ConnectedState(_globalState);
    }
    return this;
}

void ConnectedState::performAction() {
    DEBUG("Attempting to establish a TCP connection");
    _globalState.tcpClient().connect(SERVER_TCP_IP, SERVER_TCP_PORT);
}
