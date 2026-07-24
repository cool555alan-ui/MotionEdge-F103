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
static uint8_t s_tx_buffer[PROTOCOL_MAX_FRAME_SIZE];
static ByteRingBuffer_t s_rx_buffer;
static ProtocolParser_t s_parser;
static uint16_t s_telemetry_sequence;
static uint32_t s_last_telemetry_ms;
static uint32_t s_telemetry_count;
static bool s_initialized;

static bool SendFrame(const ProtocolFrame_t *frame)
{
    size_t written;
    return ProtocolFrame_Encode(
               frame, s_tx_buffer, sizeof(s_tx_buffer), &written) &&
           (BspUart_Write(s_tx_buffer, written) == BSP_UART_OK);
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
        if ((ProtocolParser_ProcessByte(&s_parser, byte, &request) ==
             PROTOCOL_PARSE_FRAME_READY) &&
            CommandService_Process(&request, &response))
        {
            (void)SendFrame(&response);
        }
    }
}

static void SendTelemetry(uint32_t now_ms)
{
    RuntimeConfig_t config;
    ProtocolFrame_t frame;
    MotionFrame_t motion;

    if (!CommandService_IsProtocolMode() || !ConfigService_Get(&config) ||
        !config.telemetry_enabled ||
        ((uint32_t)(now_ms - s_last_telemetry_ms) < config.telemetry_period_ms))
    {
        return;
    }
    s_last_telemetry_ms = now_ms;
    ++s_telemetry_sequence;
    ++s_telemetry_count;
    if (MotionService_GetLatestFrame(&motion) &&
        TelemetryService_BuildMotion(&motion, s_telemetry_sequence, &frame))
    {
        (void)SendFrame(&frame);
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
            (void)SendFrame(&frame);
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
    s_initialized = true;
    return true;
}

void CommunicationService_RunOnce(uint32_t now_ms)
{
    if (!s_initialized)
    {
        return;
    }
    ReceiveBytes();
    ParseCommands();
    SendTelemetry(now_ms);
}

bool CommunicationService_IsProtocolMode(void)
{
    return s_initialized && CommandService_IsProtocolMode();
}
