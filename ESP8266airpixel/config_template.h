// Rename this file to `config.h`, edit the values, and place it next to the airpixel sketch


// Set to 1 for debug output on the serial port
// Set to 0 for improved performance (roughly x6 improvement in maximum refresh rate)
#define DEBUG_MODE 1

// Baud rate for debug output. Depending on your arduino device you may need to change this.
// If DEBUG_MODE is disabled then you can completely ignore this value.
#define SERIAL_BAUD 115200

// Replace this with the number of LEDs you have in your setup
#define NUM_LEDS 60

// For most cases you can leave the part as is. You may need to use a different port if
// this one is already in use on your device.
#define PORT 50000

// Replace with the credentials for your WiFi
#define WIFI_NAME "<Your WiFi SSID>"
#define PASSWORD "<The password for your WiFi>"
