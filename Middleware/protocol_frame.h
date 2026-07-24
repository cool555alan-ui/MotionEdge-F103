#ifndef PROTOCOL_FRAME_H
#define PROTOCOL_FRAME_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "protocol_constants.h"

typedef struct
{
    uint8_t version;
    uint8_t type;
    uint8_t flags;
    uint16_t sequence;
    uint16_t payload_length;
    uint8_t payload[PROTOCOL_MAX_PAYLOAD_SIZE];
} ProtocolFrame_t;

/** 使用小端序和CRC16编码完整协议帧。 */
bool ProtocolFrame_Encode(const ProtocolFrame_t *frame,
                          uint8_t *output,
                          size_t output_capacity,
                          size_t *written);
/** 严格校验版本、长度和CRC后解码完整帧。 */
bool ProtocolFrame_Decode(const uint8_t *data,
                          size_t length,
                          ProtocolFrame_t *frame);
size_t ProtocolFrame_GetEncodedSize(const ProtocolFrame_t *frame);

#endif /* PROTOCOL_FRAME_H */
