#include <state.h>
#include <activeState.h>

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
        DEBUG("CHANGING STATES");
        currentState->onExit();
        DEBUG(currentState->name());
        DEBUG("^^ EXIT  ^^");
        delete currentState;
        currentState = nextState;
        DEBUG("vv ENTER vv");
        DEBUG(currentState->name());
        currentState->onEnter();
    }

    currentState->performAction();
}
