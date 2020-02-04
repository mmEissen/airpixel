#include "globalState.h"

#include <WiFiNINA.h>

#include "state.h"
#include "disconnectedState.h"
#include "connectedState.h"


State* GlobalState::nextState() {
    if (WiFi.status() != WL_CONNECTED) {
        DEBUG("GLOBAL: Wifi Disconnected");
        return new DisconnectedState(*this);
    }
    if (!_tcpClient.connected()) {
        DEBUG("GLOBAL: TCP Disconnected");
        return new ConnectedState(*this);
    }
    return NULL;
}
