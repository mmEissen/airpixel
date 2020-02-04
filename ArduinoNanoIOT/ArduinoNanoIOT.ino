#include <SPI.h>
#include <WiFiNINA.h>

#include <state.h>


GlobalState globalState;
State* currentState;

void setup() {
    #if DEBUG_MODE
        Serial.begin(SERIAL_BAUD);
        while (!Serial) {;}
    #endif

    if (WiFi.firmwareVersion() < WIFI_FIRMWARE_LATEST_VERSION) {
        DEBUG("Please upgrade the firmware");
    }

    DEBUG("STARTING");
    globalState = GlobalState();
    currentState = globalState.nextState();
    currentState->onEnter();
    DEBUG(currentState->name());
    DEBUG("SETUP COMPLETE");
}


void loop() {
    State* nextState = globalState.nextState();
    if (!nextState) {
        nextState = currentState->checkTransition();
    }

    if (nextState != currentState) {
        currentState->onExit();
        delete currentState;
        currentState = nextState;
        currentState->onEnter();
        DEBUG(currentState->name());
    }

    currentState->performAction();
}
