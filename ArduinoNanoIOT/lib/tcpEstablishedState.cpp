#include "tcpEstablishedState.h"

#include <WiFiNINA.h>

#include "constants.h"
#include "disconnectedState.h"


State* TcpEstablishedState::checkTransition() {
    return this;
}

void TcpEstablishedState::performAction() {
}
