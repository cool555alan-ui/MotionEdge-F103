#include <stdio.h>
#include <string.h>

#include "app_config.h"
#include "byte_ring_buffer.h"
#include "command_service.h"
#include "config_service.h"
#include "crc16.h"
#include "health_service.h"
#include "motion_service.h"
#include "protocol_frame.h"
#include "protocol_parser.h"
#include "telemetry_service.h"
#include "test_support.h"

static void BytesToHex(const uint8_t *data,
                       size_t length,
                       char *output,
                       size_t output_size)
{
    static const char digits[] = "0123456789abcdef";
    size_t index;

    if ((data == NULL) || (output == NULL) ||
        (output_size < (length * 2U + 1U)))
    {
        return;
    }
    for (index = 0U; index < length; ++index)
    {
        output[index * 2U] = digits[data[index] >> 4U];
        output[index * 2U + 1U] = digits[data[index] & 0x0FU];
    }
    output[length * 2U] = '\0';
}

static void ExpectGoldenJsonContains(TestContext_t *context,
                                     const uint8_t *data,
                                     size_t length)
{
    FILE *stream;
    char json[4096];
    char hex[PROTOCOL_MAX_FRAME_SIZE * 2U + 1U];
    size_t bytes_read;

    stream = fopen(PROTOCOL_VECTOR_PATH, "rb");
    TEST_EXPECT(context, stream != NULL);
    if (stream == NULL)
    {
        return;
    }
    bytes_read = fread(json, 1U, sizeof(json) - 1U, stream);
    (void)fclose(stream);
    json[bytes_read] = '\0';
    BytesToHex(data, length, hex, sizeof(hex));
    TEST_EXPECT(context, strstr(json, hex) != NULL);
}

static void TestCrcAndRing(TestContext_t *context)
{
    static const uint8_t vector[] = "123456789";
    uint8_t storage[4];
    uint8_t byte;
    ByteRingBuffer_t ring;
    uint16_t crc;

    TEST_EXPECT(context,
                Crc16CcittFalse_Calculate(vector, sizeof(vector) - 1U) == 0x29B1U);
    TEST_EXPECT(context, Crc16CcittFalse_Calculate(NULL, 0U) == 0xFFFFU);
    crc = Crc16CcittFalse_Update(0xFFFFU, vector, 4U);
    crc = Crc16CcittFalse_Update(crc, &vector[4], 5U);
    TEST_EXPECT(context, crc == 0x29B1U);
    TEST_EXPECT(context, !ByteRingBuffer_Init(NULL, storage, sizeof(storage)));
    TEST_EXPECT(context, ByteRingBuffer_Init(&ring, storage, sizeof(storage)));
    TEST_EXPECT(context, ByteRingBuffer_Size(&ring) == 0U);
    TEST_EXPECT(context, !ByteRingBuffer_Pop(&ring, &byte));
    TEST_EXPECT(context, ByteRingBuffer_Push(&ring, 1U));
    TEST_EXPECT(context, ByteRingBuffer_Push(&ring, 2U));
    TEST_EXPECT(context, ByteRingBuffer_Push(&ring, 3U));
    TEST_EXPECT(context, ByteRingBuffer_Push(&ring, 4U));
    TEST_EXPECT(context, !ByteRingBuffer_Push(&ring, 5U));
    TEST_EXPECT(context, ring.overflow_count == 1U);
    TEST_EXPECT(context, ByteRingBuffer_Pop(&ring, &byte) && (byte == 1U));
    TEST_EXPECT(context, ByteRingBuffer_Push(&ring, 5U));
    TEST_EXPECT(context, ByteRingBuffer_Peek(&ring, 3U, &byte) && (byte == 5U));
    ByteRingBuffer_Clear(&ring);
    TEST_EXPECT(context, ByteRingBuffer_FreeSpace(&ring) == sizeof(storage));
}

static void TestFrameAndParser(TestContext_t *context)
{
    static const uint8_t golden_ping[] = {
        0xA5U, 0x5AU, 0x01U, 0x01U, 0x00U, 0x34U,
        0x12U, 0x00U, 0x00U, 0x14U, 0xC7U};
    ProtocolFrame_t source = {0};
    ProtocolFrame_t decoded;
    ProtocolFrame_t parsed;
    ProtocolParser_t parser;
    uint8_t encoded[PROTOCOL_MAX_FRAME_SIZE];
    uint8_t corrupted[PROTOCOL_MAX_FRAME_SIZE];
    size_t written;
    size_t index;
    uint32_t ready = 0U;

    source.version = PROTOCOL_VERSION;
    source.type = PROTOCOL_TYPE_PING;
    source.sequence = 0x1234U;
    TEST_EXPECT(context,
                ProtocolFrame_Encode(&source, encoded, sizeof(encoded), &written));
    TEST_EXPECT(context, written == PROTOCOL_FIXED_SIZE);
    TEST_EXPECT(context,
                memcmp(encoded, golden_ping, sizeof(golden_ping)) == 0);
    ExpectGoldenJsonContains(context, encoded, written);
    TEST_EXPECT(context, encoded[5] == 0x34U);
    TEST_EXPECT(context, encoded[6] == 0x12U);
    TEST_EXPECT(context, ProtocolFrame_Decode(encoded, written, &decoded));
    TEST_EXPECT(context, decoded.sequence == source.sequence);
    TEST_EXPECT(context, !ProtocolFrame_Decode(encoded, written - 1U, &decoded));

    source.type = PROTOCOL_TYPE_SET_CONFIG;
    source.sequence = 2U;
    source.payload_length = PROTOCOL_MAX_PAYLOAD_SIZE;
    for (index = 0U; index < source.payload_length; ++index)
    {
        source.payload[index] = (uint8_t)index;
    }
    TEST_EXPECT(context,
                ProtocolFrame_Encode(&source, encoded, sizeof(encoded), &written));
    TEST_EXPECT(context, written == PROTOCOL_MAX_FRAME_SIZE);
    ExpectGoldenJsonContains(context, encoded, written);
    TEST_EXPECT(context, ProtocolFrame_Decode(encoded, written, &decoded));
    TEST_EXPECT(context,
                memcmp(source.payload, decoded.payload, source.payload_length) == 0);

    source.type = PROTOCOL_TYPE_PING;
    source.sequence = 0x1234U;
    source.payload_length = 0U;
    TEST_EXPECT(context,
                ProtocolFrame_Encode(&source, encoded, sizeof(encoded), &written));
    ProtocolParser_Init(&parser);
    TEST_EXPECT(context,
                ProtocolParser_ProcessByte(&parser, 0x11U, &parsed) ==
                    PROTOCOL_PARSE_NONE);
    for (index = 0U; index < written; ++index)
    {
        if (ProtocolParser_ProcessByte(&parser, encoded[index], &parsed) ==
            PROTOCOL_PARSE_FRAME_READY)
        {
            ++ready;
        }
    }
    TEST_EXPECT(context, ready == 1U);
    TEST_EXPECT(context, parsed.sequence == 0x1234U);

    (void)memcpy(corrupted, encoded, written);
    corrupted[written - 1U] ^= 0x80U;
    for (index = 0U; index < written; ++index)
    {
        (void)ProtocolParser_ProcessByte(&parser, corrupted[index], &parsed);
    }
    TEST_EXPECT(context, parser.crc_errors == 1U);
    for (index = 0U; index < written; ++index)
    {
        (void)ProtocolParser_ProcessByte(&parser, encoded[index], &parsed);
    }
    TEST_EXPECT(context, parser.successful_frames == 2U);

    ProtocolParser_Init(&parser);
    (void)ProtocolParser_ProcessByte(&parser, PROTOCOL_SOF1, &parsed);
    (void)ProtocolParser_ProcessByte(&parser, PROTOCOL_SOF2, &parsed);
    TEST_EXPECT(context,
                ProtocolParser_ProcessByte(&parser, 2U, &parsed) ==
                    PROTOCOL_PARSE_VERSION_ERROR);

    ProtocolParser_Init(&parser);
    (void)ProtocolParser_ProcessByte(&parser, PROTOCOL_SOF1, &parsed);
    (void)ProtocolParser_ProcessByte(&parser, PROTOCOL_SOF2, &parsed);
    (void)ProtocolParser_ProcessByte(&parser, PROTOCOL_VERSION, &parsed);
    (void)ProtocolParser_ProcessByte(&parser, PROTOCOL_TYPE_PING, &parsed);
    (void)ProtocolParser_ProcessByte(&parser, 0U, &parsed);
    (void)ProtocolParser_ProcessByte(&parser, 0U, &parsed);
    (void)ProtocolParser_ProcessByte(&parser, 0U, &parsed);
    (void)ProtocolParser_ProcessByte(&parser, 0xFFU, &parsed);
    TEST_EXPECT(context,
                ProtocolParser_ProcessByte(&parser, 0x00U, &parsed) ==
                    PROTOCOL_PARSE_LENGTH_ERROR);
    for (index = 0U; index < sizeof(golden_ping); ++index)
    {
        (void)ProtocolParser_ProcessByte(&parser, golden_ping[index], &parsed);
    }
    TEST_EXPECT(context, parser.successful_frames == 1U);

    ready = 0U;
    ProtocolParser_Init(&parser);
    for (index = 0U; index < (sizeof(golden_ping) * 2U); ++index)
    {
        if (ProtocolParser_ProcessByte(
                &parser,
                golden_ping[index % sizeof(golden_ping)],
                &parsed) == PROTOCOL_PARSE_FRAME_READY)
        {
            ++ready;
        }
    }
    TEST_EXPECT(context, ready == 2U);
}

static void TestConfigCommandTelemetry(TestContext_t *context)
{
    RuntimeConfig_t original;
    RuntimeConfig_t update;
    RuntimeConfig_t current;
    ProtocolFrame_t request = {0};
    ProtocolFrame_t response;
    MotionFrame_t motion = {0};
    ProtocolFrame_t telemetry;

    TEST_EXPECT(context, MotionService_Init(0U));
    TEST_EXPECT(context, CommandService_Init());
    TEST_EXPECT(context, ConfigService_Get(&original));
    update = original;
    update.telemetry_period_ms = 250U;
    update.low_pass_alpha_milli = 300U;
    TEST_EXPECT(context, ConfigService_Set(&update));
    TEST_EXPECT(context, ConfigService_Get(&current));
    TEST_EXPECT(context, current.telemetry_period_ms == 250U);
    TEST_EXPECT(context,
                CommandService_GetMode() ==
                    COMMAND_SERVICE_MODE_DEVELOPMENT);
    update.sensor_sample_period_ms = 1U;
    TEST_EXPECT(context, !ConfigService_Set(&update));
    TEST_EXPECT(context, ConfigService_Get(&current));
    TEST_EXPECT(context, current.telemetry_period_ms == 250U);
    TEST_EXPECT(context,
                current.sensor_sample_period_ms == original.sensor_sample_period_ms);

    request.version = PROTOCOL_VERSION;
    request.type = 0x7FU;
    request.sequence = 77U;
    TEST_EXPECT(context, CommandService_Process(&request, &response));
    TEST_EXPECT(context, response.sequence == 77U);
    TEST_EXPECT(context, response.payload[1] == PROTOCOL_STATUS_INVALID_COMMAND);
    request.type = PROTOCOL_TYPE_PING;
    request.payload_length = 1U;
    TEST_EXPECT(context, CommandService_Process(&request, &response));
    TEST_EXPECT(context, response.payload[1] == PROTOCOL_STATUS_INVALID_LENGTH);
    request.type = PROTOCOL_TYPE_START_CALIBRATION;
    request.payload_length = 0U;
    TEST_EXPECT(context, CommandService_Process(&request, &response));
    TEST_EXPECT(context, response.payload[1] == PROTOCOL_STATUS_OK);
    request.type = PROTOCOL_TYPE_GET_LATEST_MOTION;
    TEST_EXPECT(context, CommandService_Process(&request, &response));
    TEST_EXPECT(context, response.payload[1] == PROTOCOL_STATUS_NOT_READY);
    request.type = PROTOCOL_TYPE_SET_STREAM_STATE;
    request.payload_length = 1U;
    request.payload[0] = 1U;
    TEST_EXPECT(context, CommandService_Process(&request, &response));
    TEST_EXPECT(context, response.payload[1] == PROTOCOL_STATUS_OK);
    TEST_EXPECT(context,
                CommandService_GetMode() == COMMAND_SERVICE_MODE_PROTOCOL);
    request.payload[0] = 0U;
    TEST_EXPECT(context, CommandService_Process(&request, &response));
    TEST_EXPECT(context,
                CommandService_GetMode() ==
                    COMMAND_SERVICE_MODE_DEVELOPMENT);

    motion.valid = true;
    motion.attitude.valid = true;
    motion.calibrated = true;
    motion.timestamp_ms = 10U;
    TEST_EXPECT(context,
                TelemetryService_BuildMotion(&motion, 5U, &telemetry));
    TEST_EXPECT(context,
                telemetry.payload_length == TELEMETRY_MOTION_PAYLOAD_SIZE);
    TEST_EXPECT(context, telemetry.sequence == 5U);

    {
        HealthSnapshot_t health;
        MotionServiceStats_t motion_stats;
        TelemetryProtocolStats_t protocol_stats = {1U, 2U, 3U, 4U};
        HealthService_Init(0U);
        HealthService_RecordLoop(25U);
        TEST_EXPECT(context, HealthService_GetSnapshot(&health));
        TEST_EXPECT(context, MotionService_GetStats(&motion_stats));
        TEST_EXPECT(context,
                    TelemetryService_BuildHealth(&health,
                                                 MotionService_GetState(),
                                                 &motion_stats,
                                                 &protocol_stats,
                                                 6U,
                                                 &telemetry));
        TEST_EXPECT(context,
                    telemetry.payload_length ==
                        TELEMETRY_HEALTH_PAYLOAD_SIZE);
    }
}

void TestProtocol_Run(TestContext_t *context)
{
    TestCrcAndRing(context);
    TestFrameAndParser(context);
    TestConfigCommandTelemetry(context);
}
