#pragma once
#include "config.h"

#if DEBUG_MODE
#define DEBUG(MSG) Serial.println(MSG)
#define SERIAL_BAUD  115200
#else
#define DEBUG(MSG)
#endif

#define LOCAL_UDP_PORT 50001
#define LOCAL_UDP_PORT_CHARS "\xC3\x51"
#define CHARS_IN_UINT64 ( sizeof(uint64_t) / sizeof(uint8_t) )

#define UDP_MAX_PACKET_SIZE 65507
