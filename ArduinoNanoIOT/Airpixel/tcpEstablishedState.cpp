#include "tcpEstablishedState.h"

#include <SPI.h>
#include <WiFiNINA.h>

#include "constants.h"
#include "activeState.h"


State* TcpEstablishedState::checkTransition() {
    return new ActiveState(_globalState);
}

void TcpEstablishedState::performAction() {
    _globalState.tcpClient().write(LOCAL_UDP_PORT_CHARS);
    _globalState.tcpClient().write(DEVICE_ID);
    _globalState.tcpClient().write('\n');
    _globalState.tcpClient().flush();
}
