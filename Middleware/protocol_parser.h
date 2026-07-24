#ifndef PROTOCOL_PARSER_H
#define PROTOCOL_PARSER_H

#include <stddef.h>
#include <stdint.h>

#include "protocol_frame.h"

typedef enum
{
    PROTOCOL_PARSE_NONE = 0,
    PROTOCOL_PARSE_FRAME_READY,
    PROTOCOL_PARSE_CRC_ERROR,
    PROTOCOL_PARSE_LENGTH_ERROR,
    PROTOCOL_PARSE_VERSION_ERROR
} ProtocolParseResult_t;

typedef struct
{
    uint8_t buffer[PROTOCOL_MAX_FRAME_SIZE];
    size_t received;
    size_t expected;
    uint32_t successful_frames;
    uint32_t crc_errors;
    uint32_t length_errors;
    uint32_t version_errors;
    uint32_t discarded_bytes;
} ProtocolParser_t;

/** 清空流式解析状态和统计。 */
void ProtocolParser_Init(ProtocolParser_t *parser);
/** 消费一个字节，并在完整帧或错误时返回状态。 */
ProtocolParseResult_t ProtocolParser_ProcessByte(ProtocolParser_t *parser,
                                                 uint8_t byte,
                                                 ProtocolFrame_t *frame);

#endif /* PROTOCOL_PARSER_H */
