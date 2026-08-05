#include "communication_service.h"

#include <stddef.h>

#include "bsp_uart.h"
#include "byte_ring_buffer.h"
#include "command_service.h"
#include "config_service.h"
#include "health_service.h"
#include "motion_service.h"
#include "protocol_parser.h"
#include "telemetry_service.h"

static uint8_t s_rx_storage[PROTOCOL_RX_STORAGE_SIZE];
/* 命令响应与周期遥测分别使用固定缓冲区，避免两个RTOS任务并发编码时互相覆盖。 */
static uint8_t s_command_tx_buffer[PROTOCOL_MAX_FRAME_SIZE];
static uint8_t s_telemetry_tx_buffer[PROTOCOL_MAX_FRAME_SIZE];
static ByteRingBuffer_t s_rx_buffer;
static ProtocolParser_t s_parser;
static uint16_t s_telemetry_sequence;
static uint32_t s_last_telemetry_ms;
static uint32_t s_telemetry_count;
static bool s_initialized;
static CommunicationWriter_t s_writer;
static CommunicationCommandSink_t s_command_sink;
static uint32_t s_command_error_count;
static uint32_t s_tx_error_count;

static bool BspWriter(const uint8_t *data, size_t length)
{
    return BspUart_Write(data, length) == BSP_UART_OK;
}

static bool SendFrame(const ProtocolFrame_t *frame,
                      uint8_t *tx_buffer,
                      size_t tx_capacity)
{
    size_t written;
    if ((frame == NULL) || (tx_buffer == NULL) || (s_writer == NULL) ||
        !ProtocolFrame_Encode(frame, tx_buffer, tx_capacity, &written) ||
        !s_writer(tx_buffer, written))
    {
        ++s_tx_error_count;
        return false;
    }
    return true;
}

static void ReceiveBytes(void)
{
    uint32_t count;
    for (count = 0U; count < PROTOCOL_RX_BUDGET_PER_RUN; ++count)
    {
        uint8_t byte;
        bool received;
        if ((BspUart_TryReadByte(&byte, &received) != BSP_UART_OK) || !received)
        {
            break;
        }
        (void)ByteRingBuffer_Push(&s_rx_buffer, byte);
    }
}

static void ParseCommands(void)
{
    uint32_t count;
    for (count = 0U; count < PROTOCOL_PARSE_BUDGET_PER_RUN; ++count)
    {
        uint8_t byte;
        ProtocolFrame_t request;
        ProtocolFrame_t response;
        if (!ByteRingBuffer_Pop(&s_rx_buffer, &byte))
        {
            break;
        }
        if (ProtocolParser_ProcessByte(&s_parser, byte, &request) ==
            PROTOCOL_PARSE_FRAME_READY)
        {
            if (s_command_sink != NULL)
            {
                if (!s_command_sink(&request))
                {
                    ++s_command_error_count;
                }
            }
            else if (CommandService_Process(&request, &response))
            {
                (void)SendFrame(&response,
                                s_command_tx_buffer,
                                sizeof(s_command_tx_buffer));
            }
            else
            {
                ++s_command_error_count;
            }
        }
    }
}

void CommunicationService_RunTelemetry(uint32_t now_ms,
                                       const MotionFrame_t *motion)
{
    RuntimeConfig_t config;
    ProtocolFrame_t frame;

    if (!CommandService_IsProtocolMode() || !ConfigService_Get(&config) ||
        !config.telemetry_enabled ||
        ((uint32_t)(now_ms - s_last_telemetry_ms) < config.telemetry_period_ms))
    {
        return;
    }
    s_last_telemetry_ms = now_ms;
    ++s_telemetry_sequence;
    ++s_telemetry_count;
    if ((motion != NULL) &&
        TelemetryService_BuildMotion(motion, s_telemetry_sequence, &frame))
    {
        (void)SendFrame(&frame,
                        s_telemetry_tx_buffer,
                        sizeof(s_telemetry_tx_buffer));
    }
    if ((s_telemetry_count % 10U) == 0U)
    {
        HealthSnapshot_t health;
        MotionServiceStats_t motion_stats;
        TelemetryProtocolStats_t protocol_stats = {
            0U,
            s_parser.successful_frames,
            s_parser.crc_errors,
            s_rx_buffer.overflow_count};
        if (HealthService_GetSnapshot(&health) &&
            MotionService_GetStats(&motion_stats) &&
            TelemetryService_BuildHealth(&health,
                                         MotionService_GetState(),
                                         &motion_stats,
                                         &protocol_stats,
                                         ++s_telemetry_sequence,
                                         &frame))
        {
            (void)SendFrame(&frame,
                            s_telemetry_tx_buffer,
                            sizeof(s_telemetry_tx_buffer));
        }
    }
}

bool CommunicationService_Init(uint32_t now_ms)
{
    if (!ByteRingBuffer_Init(
            &s_rx_buffer, s_rx_storage, sizeof(s_rx_storage)) ||
        !CommandService_Init())
    {
        return false;
    }
    ProtocolParser_Init(&s_parser);
    s_telemetry_sequence = 0U;
    s_last_telemetry_ms = now_ms;
    s_telemetry_count = 0U;
    s_writer = BspWriter;
    s_command_sink = NULL;
    s_command_error_count = 0U;
    s_tx_error_count = 0U;
    s_initialized = true;
    return true;
}

void CommunicationService_SetWriter(CommunicationWriter_t writer)
{
    s_writer = (writer != NULL) ? writer : BspWriter;
}

void CommunicationService_SetCommandSink(CommunicationCommandSink_t sink)
{
    s_command_sink = sink;
}

void CommunicationService_RunRxOnce(void)
{
    if (!s_initialized)
    {
        return;
    }
    ReceiveBytes();
    ParseCommands();
}

bool CommunicationService_ProcessCommand(const ProtocolFrame_t *request)
{
    ProtocolFrame_t response;

    if (!s_initialized || !CommandService_Process(request, &response))
    {
        ++s_command_error_count;
        return false;
    }
    return SendFrame(&response,
                     s_command_tx_buffer,
                     sizeof(s_command_tx_buffer));
}

void CommunicationService_RunOnce(uint32_t now_ms)
{
    if (!s_initialized)
    {
        return;
    }
    {
        MotionFrame_t motion;
        CommunicationService_RunRxOnce();
        CommunicationService_RunTelemetry(
            now_ms, MotionService_GetLatestFrame(&motion) ? &motion : NULL);
    }
}

bool CommunicationService_IsProtocolMode(void)
{
    return s_initialized && CommandService_IsProtocolMode();
}

bool CommunicationService_GetStats(CommunicationServiceStats_t *stats)
{
    if ((stats == NULL) || !s_initialized)
    {
        return false;
    }
    stats->rx_overflow_count =
        s_rx_buffer.overflow_count + BspUart_GetRxOverflowCount();
    stats->successful_frames = s_parser.successful_frames;
    stats->crc_error_count = s_parser.crc_errors;
    stats->parser_error_count = s_parser.length_errors + s_parser.version_errors;
    stats->command_error_count = s_command_error_count;
    stats->tx_error_count = s_tx_error_count;
    stats->uart_error_count = BspUart_GetRxErrorCount();
    return true;
}
