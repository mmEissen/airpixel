#include <state.h>
#include <cstring>

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
    globalState.begin();
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

    if (strcmp(nextState->name(), currentState->name())) {
        DEBUG("CHANGING STATES:");
        DEBUG(currentState->name());
        DEBUG(nextState->name());
        currentState->onExit();
        delete currentState;
        currentState = nextState;
        currentState->onEnter();
        DEBUG("STATE CHANGE COMPLETE");
    }

    currentState->performAction();
}
