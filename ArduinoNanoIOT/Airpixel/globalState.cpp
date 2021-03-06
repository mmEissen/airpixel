#include "globalState.h"

#include <WiFiNINA.h>

#include "state.h"
#include "disconnectedState.h"
#include "connectedState.h"


State* GlobalState::nextState() {
    if (WiFi.status() != WL_CONNECTED) {
        return new DisconnectedState(*this);
    }
    return NULL;
}
