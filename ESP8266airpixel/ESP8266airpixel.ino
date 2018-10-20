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

#define FRAME_NUMBER_BYTES 4
#define PACKET_SIZE (FRAME_NUMBER_BYTES + FRAME_SIZE)
#define KEEPALIVE_FRAME_NUMBER 0xFFFFFFFF

#define WAIT_FOR_CONNECTION_SECONDS 10
#define TIMEOUT_MILLISECONDS 10000



NeoPixelBus<NeoRgbwFeature, Neo800KbpsMethod> strip(NUM_LEDS);

WiFiServer server(PORT);
WiFiClient client = WiFiClient();
WiFiUDP udp;

uint8_t wiFiFrame[FRAME_SIZE];
unsigned long lastMessage;

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
  server.begin();
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
  client = server.available();
  if (client && client.connected()) {
    onClientConnect();
  }
}

void onClientConnect() {
  currentState = State::CLIENT_CONNECTED;
  DEBUG("client connected");
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

bool isClientConnected() {
  return client && client.connected();
}

void checkMessages() {
  if (!isClientConnected()) {
    onClientDisconnect();
    return;
  }
  auto available = udp.parsePacket();
  if (available == PACKET_SIZE) {
    lastMessage = millis();
    readMessage();
  } else {
    discardMessage();
  }
  if(isTimedOut()) {
    DEBUG("Client timed out");
    client.flush();
    client.stop();
    client = WiFiClient();
  }
}

void discardMessage() {
  while (udp.available()) {
    udp.read();
  }
}

void readMessage() {
  DEBUG("Message received");
  uint32_t frameNumber = 0;

  for (int i = 0; i < FRAME_NUMBER_BYTES; ++i) {
    frameNumber = frameNumber << 8;
    frameNumber += udp.read();
  }

  if (frameNumber == KEEPALIVE_FRAME_NUMBER) {
    DEBUG("Ignoring keepalive message");
    discardMessage();
    return;
  }

  udp.read(strip.Pixels(), FRAME_SIZE);
  strip.Dirty();
  strip.Show();

  sendFrameNumber(frameNumber);
}

void sendFrameNumber(uint32_t number) {
  udp.beginPacket(udp.remoteIP(), udp.remotePort());
  for (int i = 0; i < FRAME_NUMBER_BYTES; ++i) {
    char nextChar = static_cast<char>(number);
    udp.write(nextChar);
    number = number >> 8;
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
