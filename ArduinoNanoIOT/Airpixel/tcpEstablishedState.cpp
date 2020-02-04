#include "tcpEstablishedState.h"

#include <WiFiNINA.h>

#include "constants.h"
#include "activeState.h"


State* TcpEstablishedState::checkTransition() {
    return new ActiveState(_globalState);
}

void TcpEstablishedState::performAction() {
    char port[] = { 
        (char) (LOCAL_UDP_PORT >> sizeof(char)),
        (char) LOCAL_UDP_PORT,
    };
    _globalState.tcpClient().write(DEVICE_ID);
    _globalState.tcpClient().write(port);
    _globalState.tcpClient().write('\n');
    _globalState.tcpClient().flush();
}
