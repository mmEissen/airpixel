#include <SPI.h>
#include <WiFiNINA.h>

#include "constants.h"
#include "connectedState.h"
#include "disconnectedState.h"


State* DisconnectedState::checkTransition() {
    if (WiFi.status() == WL_AP_CONNECTED) {
        return new ConnectedState(_globalState);
    }
    return this;
}

void DisconnectedState::performAction() {
    DEBUG("Attempting to connect to WPA SSID: ");
    DEBUG(WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}
