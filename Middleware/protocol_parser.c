#include "protocol_parser.h"

#include <stddef.h>

#include "crc16.h"

static uint16_t ReadLe16(const uint8_t *input)
{
    return (uint16_t)input[0] | ((uint16_t)input[1] << 8U);
}

static void ResetFrame(ProtocolParser_t *parser)
{
    parser->received = 0U;
    parser->expected = 0U;
}

void ProtocolParser_Init(ProtocolParser_t *parser)
{
    if (parser != NULL)
    {
        *parser = (ProtocolParser_t){0};
    }
}

ProtocolParseResult_t ProtocolParser_ProcessByte(ProtocolParser_t *parser,
                                                 uint8_t byte,
                                                 ProtocolFrame_t *frame)
{
    uint16_t payload_length;
    uint16_t received_crc;
    uint16_t calculated_crc;

    if ((parser == NULL) || (frame == NULL))
    {
        return PROTOCOL_PARSE_NONE;
    }
    if (parser->received == 0U)
    {
        if (byte == PROTOCOL_SOF1)
        {
            parser->buffer[parser->received++] = byte;
        }
        else
        {
            ++parser->discarded_bytes;
        }
        return PROTOCOL_PARSE_NONE;
    }
    if (parser->received == 1U)
    {
        if (byte == PROTOCOL_SOF2)
        {
            parser->buffer[parser->received++] = byte;
        }
        else if (byte != PROTOCOL_SOF1)
        {
            ResetFrame(parser);
            ++parser->discarded_bytes;
        }
        return PROTOCOL_PARSE_NONE;
    }

    parser->buffer[parser->received++] = byte;
    if ((parser->received == 3U) && (byte != PROTOCOL_VERSION))
    {
        ++parser->version_errors;
        ResetFrame(parser);
        return PROTOCOL_PARSE_VERSION_ERROR;
    }
    if (parser->received == 9U)
    {
        payload_length = ReadLe16(&parser->buffer[7]);
        if (payload_length > PROTOCOL_MAX_PAYLOAD_SIZE)
        {
            ++parser->length_errors;
            ResetFrame(parser);
            return PROTOCOL_PARSE_LENGTH_ERROR;
        }
        parser->expected = PROTOCOL_FIXED_SIZE + payload_length;
    }
    if ((parser->expected == 0U) || (parser->received < parser->expected))
    {
        return PROTOCOL_PARSE_NONE;
    }

    payload_length = ReadLe16(&parser->buffer[7]);
    received_crc = ReadLe16(&parser->buffer[9U + payload_length]);
    calculated_crc =
        Crc16CcittFalse_Calculate(&parser->buffer[2], 7U + payload_length);
    if (received_crc != calculated_crc)
    {
        ++parser->crc_errors;
        ResetFrame(parser);
        return PROTOCOL_PARSE_CRC_ERROR;
    }
    if (!ProtocolFrame_Decode(parser->buffer, parser->expected, frame))
    {
        ResetFrame(parser);
        return PROTOCOL_PARSE_LENGTH_ERROR;
    }
    ++parser->successful_frames;
    ResetFrame(parser);
    return PROTOCOL_PARSE_FRAME_READY;
}
