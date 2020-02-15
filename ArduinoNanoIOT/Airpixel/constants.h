#pragma once
#include "config.h"

#if DEBUG_MODE
#define DEBUG(MSG) Serial.println(MSG)
#define SERIAL_BAUD  115200
#else
#define DEBUG(MSG)
#endif

#define LOCAL_UDP_PORT 50001
#define CHARS_IN_UINT64 ( sizeof(uint64_t) / sizeof(char) )

#define UDP_MAX_PACKET_SIZE 65507
#define PIXEL_COUNT 4

