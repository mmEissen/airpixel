// Rename this file to `config.h`, edit the values, and place it next to the airpixel sketch

// For most cases you can leave the port as is. You may need to use a different port if
// this one is already in use on your device.
#define PORT 50000

// Replace with the credentials for your WiFi
#define WIFI_NAME "<Your WiFi SSID>"
#define PASSWORD "<The password for your WiFi>"

#define ADVERTISING_MESSAGE "LEDRing\n"
#define ADVERTISING_MESSAGE_LENGTH 8

// Set to 1 for debug output on the serial port
// Set to 0 for improved performance (roughly x6 improvement in maximum refresh rate)
#define DEBUG_MODE 1

// Baud rate for debug output. Depending on your arduino device you may need to change this.
// If DEBUG_MODE is disabled then you can ignore this value.
#define SERIAL_BAUD 115200

// The size of the buffer alocated to the LEDs in bytes. This determines the maximum number
// of LEDs that can be controlled by the controller. The maximum number of LEDs is:
//   - (LED_BUFFER_SIZE / 4) for 4 color LEDs (RGBW or GRBW)
//   - (LED_BUFFER_SIZE / 3) for 3 color LEDs (RGB or GRB)
//
// There is no significant advantage to a smaller buffer, other than reduced memory usage
#define LED_BUFFER_SIZE 3000
