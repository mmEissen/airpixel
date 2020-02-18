#include "tcpEstablishedState.h"

#include <SPI.h>
#include <WiFiNINA.h>

#include "constants.h"
#include "activeState.h"
#include "connectedState.h"


State* TcpEstablishedState::checkTransition() {
    if (_charCount == 2) {
        return new ActiveState(_globalState);
    }
    if (_charCount > 2) {
        return new ConnectedState(_globalState);
    }
    return this;
}

void TcpEstablishedState::onEnter() {
    _globalState.tcpClient().write(LOCAL_UDP_PORT_CHARS);
    _globalState.tcpClient().write(DEVICE_ID);
    _globalState.tcpClient().write('\n');
    _globalState.tcpClient().flush();
}

void TcpEstablishedState::onExit() {
    _globalState.tcpClient().stop();
}

void TcpEstablishedState::performAction() {
    auto nextChar = _globalState.tcpClient().read();
    if (nextChar >= 0) {
        _responsePort = _responsePort << 8;
        _responsePort += nextChar;
        ++_charCount;
        DEBUG(_charCount);
        _globalState.setResponsePort(_responsePort);
    }
}
