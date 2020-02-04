#include <WiFiNINA.h>

#include "constants.h"
#include "connectedState.h"
#include "tcpEstablishedState.h"


State* ConnectedState::checkTransition() {
    if (_globalState.tcpClient().connected()) {
        return new TcpEstablishedState(_globalState);
    }
    return this;
}

void ConnectedState::performAction() {
    DEBUG(SERVER_TCP_IP);
    DEBUG(SERVER_TCP_PORT);
    _globalState.tcpClient().connect(SERVER_TCP_IP, SERVER_TCP_PORT);
}
