#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <NeoPixelBus.h>

#include "config.h"

#if DEBUG_MODE
#define DEBUG(MSG) Serial.println(MSG)
#else
#define DEBUG(MSG)
#endif


#define NUM_COLORS 4
#define FRAME_SIZE NUM_COLORS * NUM_LEDS

#define FRAME_NUMBER_BYTES 8
#define PORT_NUMBER_BYTES 4
#define PACKET_SIZE (FRAME_NUMBER_BYTES + FRAME_SIZE)

#define DISCONNECT_FRAME_NUMBER 0xFFFFFFFFFFFFFFFF
#define CONNECT_FRAME_NUMBER 0xFFFFFFFFFFFFFFFE
#define HEARTBEAT_FRAME_NUMBER 0xFFFFFFFFFFFFFFFD

#define WAIT_FOR_CONNECTION_SECONDS 10
#define TIMEOUT_MILLISECONDS 5000



NeoPixelBus<NeoRgbwFeature, Neo800KbpsMethod> strip(NUM_LEDS);

WiFiUDP udp;
IPAddress connectedIP;
unsigned long lastMessage;
uint32_t clientReceivePort;
uint64_t lastFrameNumber;

enum class State {
  DISCONNECTED,
  WIFI_CONNECTED,
  CLIENT_CONNECTED,
};

State currentState;

void setup() {
#if DEBUG_MODE
  Serial.begin(SERIAL_BAUD);
#endif

  DEBUG("SETUP");
  currentState = State::DISCONNECTED;
  lastFrameNumber = 0;
  strip.Begin();
}

void advertise() {
  DEBUG("ADVERTISING...");
  auto myIp = WiFi.localIP();
  auto subnetMask = WiFi.subnetMask();
  IPAddress subnet(myIp & subnetMask);
  IPAddress broadcast(myIp | ~subnetMask);
  udp.beginPacket(broadcast, PORT);
  udp.write("LEDRing\n", 8);
  udp.endPacket();
}

void connectToWiFi() {
  WiFi.begin(WIFI_NAME, PASSWORD);
  int seconds = 0;
  while (WiFi.status() != WL_CONNECTED && seconds < WAIT_FOR_CONNECTION_SECONDS) {
    delay(1000);
    ++seconds;
  }
  if (WiFi.status() == WL_CONNECTED) {
    onWiFiConnect();
  } else {
    switch (WiFi.status()) {
      case WL_IDLE_STATUS:
        DEBUG("WL_IDLE_STATUS"); break;
      case WL_NO_SHIELD:
        DEBUG("WL_NO_SHIELD"); break;
      case WL_NO_SSID_AVAIL:
        DEBUG("WL_NO_SSID_AVAIL"); break;
      case WL_SCAN_COMPLETED:
        DEBUG("WL_SCAN_COMPLETED"); break;
      case WL_CONNECT_FAILED:
        DEBUG("WL_CONNECT_FAILED"); break;
      case WL_CONNECTION_LOST:
        DEBUG("WL_CONNECTION_LOST"); break;
      case WL_DISCONNECTED:
        DEBUG("WL_DISCONNECTED"); break;
    }
  }
}

void onWiFiConnect() {
  currentState = State::WIFI_CONNECTED;
  DEBUG("WiFi connected.");
  DEBUG(WiFi.localIP());
  udp.begin(PORT);
}

void onWiFiDisconnect() {
  currentState = State::DISCONNECTED;
  DEBUG("WiFi disconnected.");
}

void connectToClient() {
  if (WiFi.status() != WL_CONNECTED) {
    onWiFiDisconnect();
    return;
  }
  advertise();
  delay(100);

  uint64_t available;
  while (available = udp.parsePacket()) {
    
    if (available != FRAME_NUMBER_BYTES + PORT_NUMBER_BYTES){
      continue;
    }

    auto frameNumber = readFrameNumber();
    if (frameNumber == CONNECT_FRAME_NUMBER) {
      onClientConnect();
      return;
    }
  }
}

uint32_t getPortNumber() {
  uint32_t port = 0;

  for (int i = 0; i < 4; ++i) {
    port = port << 8;
    port += udp.read();
  }

  return port;
}

void onClientConnect() {
  currentState = State::CLIENT_CONNECTED;
  connectedIP = udp.remoteIP();
  clientReceivePort = getPortNumber();
  DEBUG("client connected");
  DEBUG(connectedIP);
  DEBUG(clientReceivePort);
  sendFrameNumber(CONNECT_FRAME_NUMBER);
  lastMessage = millis();
}

void onClientDisconnect() {
  currentState = State::WIFI_CONNECTED;
  DEBUG("client disconnected");
  strip.ClearTo(RgbwColor(0));
  strip.Show();
}

bool isTimedOut() {
  // has to handle overflow of millis

  auto now = millis();

  auto backwardThreshold = now - TIMEOUT_MILLISECONDS;
  auto forwardThreshold = lastMessage + TIMEOUT_MILLISECONDS;

  if (forwardThreshold < now && backwardThreshold >= lastMessage) {
    return true;
  }
  if (forwardThreshold >= now && backwardThreshold < lastMessage) {
    return false;
  }
  return now < lastMessage;
}

void checkMessages() {
  auto available = udp.parsePacket();

  if (available && udp.remoteIP() == connectedIP) {
    if (available == PACKET_SIZE) {
      readMessage();
    }
    if (available == FRAME_NUMBER_BYTES) {
      readCommand();
    }
  }

  if (available == PACKET_SIZE && udp.remoteIP() == connectedIP) {
    lastMessage = millis();
    readMessage();
  }

  if(isTimedOut()) {
    DEBUG("Client timed out");
    onClientDisconnect();
  }
}

uint64_t readFrameNumber() {
  uint64_t frameNumber = 0;

  for (int i = 0; i < FRAME_NUMBER_BYTES; ++i) {
    frameNumber = frameNumber << 8;
    frameNumber += udp.read();
  }

  return frameNumber;
}

void readCommand() {
  DEBUG("Command received");
  auto frameNumber = readFrameNumber();

  if (frameNumber == HEARTBEAT_FRAME_NUMBER) {
    DEBUG("KEEP ALIVE MESSAGE");
    lastMessage = millis();
    sendFrameNumber(frameNumber);
    return;
  }

  if (frameNumber == DISCONNECT_FRAME_NUMBER) {
    DEBUG("DISCONNECT MESSAGE");
    sendFrameNumber(frameNumber);
    onClientDisconnect();
    return;
  }
  
  if (frameNumber == CONNECT_FRAME_NUMBER) {
    DEBUG("IGNORING CONNECTION MESSAGE");
    return;
  }
}

void readMessage() {
  DEBUG("Message received");
  lastMessage = millis();
  auto frameNumber = readFrameNumber();

  if (frameNumber <= lastFrameNumber) {
    DEBUG("DISCARDING OUT OF ORDER FRAME");
    sendFrameNumber(frameNumber);
    return;
  }

  udp.read(strip.Pixels(), FRAME_SIZE);
  strip.Dirty();
  strip.Show();

  lastFrameNumber = frameNumber;
  sendFrameNumber(frameNumber);
}

void sendFrameNumber(uint64_t number) {
  udp.beginPacket(connectedIP, clientReceivePort);
  for (int i = 0; i < FRAME_NUMBER_BYTES; ++i) {
    char nextChar = static_cast<char>(number >> ((FRAME_NUMBER_BYTES - 1) * 8));
    udp.write(nextChar);
    number = number << 8;
  }
  udp.endPacket();
}

void loop() {
  switch (currentState) {
    case State::DISCONNECTED:
      connectToWiFi();
      break;
    case State::WIFI_CONNECTED:
      connectToClient();
      break;
    case State::CLIENT_CONNECTED:
      checkMessages();
      break;
  }
}
