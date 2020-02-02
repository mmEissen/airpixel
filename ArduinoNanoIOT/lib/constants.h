#include "../config.h"

#if DEBUG_MODE
#define DEBUG(MSG) Serial.println(MSG)
#define SERIAL_BAUD  115200
#else
#define DEBUG(MSG)
#endif

#define SERVER_TCP_IP "192.168.2.1"
#define SERVER_TCP_PORT 50000

#define UDP_RECEIVE_PORT
