#include "protocol_frame.h"

#include <string.h>

#include "crc16.h"

static void WriteLe16(uint8_t *output, uint16_t value)
{
    output[0] = (uint8_t)value;
    output[1] = (uint8_t)(value >> 8U);
}

static uint16_t ReadLe16(const uint8_t *input)
{
    return (uint16_t)input[0] | ((uint16_t)input[1] << 8U);
}

size_t ProtocolFrame_GetEncodedSize(const ProtocolFrame_t *frame)
{
    if ((frame == NULL) ||
        (frame->payload_length > PROTOCOL_MAX_PAYLOAD_SIZE))
    {
        return 0U;
    }
    return PROTOCOL_FIXED_SIZE + frame->payload_length;
}

bool ProtocolFrame_Encode(const ProtocolFrame_t *frame,
                          uint8_t *output,
                          size_t output_capacity,
                          size_t *written)
{
    size_t size = ProtocolFrame_GetEncodedSize(frame);
    uint16_t crc;

    if ((frame == NULL) || (output == NULL) || (written == NULL) ||
        (frame->version != PROTOCOL_VERSION) || (size == 0U) ||
        (output_capacity < size))
    {
        return false;
    }
    *written = 0U;
    output[0] = PROTOCOL_SOF1;
    output[1] = PROTOCOL_SOF2;
    output[2] = frame->version;
    output[3] = frame->type;
    output[4] = frame->flags;
    WriteLe16(&output[5], frame->sequence);
    WriteLe16(&output[7], frame->payload_length);
    if (frame->payload_length != 0U)
    {
        (void)memcpy(&output[9], frame->payload, frame->payload_length);
    }
    /* CRC覆盖VERSION至Payload末尾，不包含SOF和CRC字段。 */
    crc = Crc16CcittFalse_Calculate(&output[2], 7U + frame->payload_length);
    WriteLe16(&output[9U + frame->payload_length], crc);
    *written = size;
    return true;
}

bool ProtocolFrame_Decode(const uint8_t *data,
                          size_t length,
                          ProtocolFrame_t *frame)
{
    uint16_t payload_length;
    uint16_t expected_crc;
    uint16_t actual_crc;

    if ((data == NULL) || (frame == NULL) || (length < PROTOCOL_FIXED_SIZE) ||
        (data[0] != PROTOCOL_SOF1) || (data[1] != PROTOCOL_SOF2) ||
        (data[2] != PROTOCOL_VERSION))
    {
        return false;
    }
    payload_length = ReadLe16(&data[7]);
    if ((payload_length > PROTOCOL_MAX_PAYLOAD_SIZE) ||
        (length != (PROTOCOL_FIXED_SIZE + payload_length)))
    {
        return false;
    }
    expected_crc = ReadLe16(&data[9U + payload_length]);
    actual_crc = Crc16CcittFalse_Calculate(&data[2], 7U + payload_length);
    if (expected_crc != actual_crc)
    {
        return false;
    }
    frame->version = data[2];
    frame->type = data[3];
    frame->flags = data[4];
    frame->sequence = ReadLe16(&data[5]);
    frame->payload_length = payload_length;
    if (payload_length != 0U)
    {
        (void)memcpy(frame->payload, &data[9], payload_length);
    }
    return true;
}
