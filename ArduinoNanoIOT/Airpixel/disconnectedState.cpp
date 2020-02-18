#include <SPI.h>
#include <WiFiNINA.h>

#include "constants.h"
#include "connectedState.h"
#include "disconnectedState.h"


State* DisconnectedState::checkTransition() {
    if (WiFi.status() == WL_CONNECTED) {
        return new ConnectedState(_globalState);
    }
    return this;
}

void DisconnectedState::performAction() {
    auto status = WiFi.status();
    if (status == WL_CONNECTED) {
        return;
    }
    if (status == WL_IDLE_STATUS && is_connecting){
        delay(100);
    }
    else {
        DEBUG("Attempting to connect to WPA SSID: ");
        DEBUG(WIFI_SSID);
        DEBUG(status);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        is_connecting = true;
    }
}
