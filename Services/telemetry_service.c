#include "telemetry_service.h"

#include <stddef.h>

static void Put32(uint8_t *data, uint32_t value)
{
    data[0] = (uint8_t)value;
    data[1] = (uint8_t)(value >> 8U);
    data[2] = (uint8_t)(value >> 16U);
    data[3] = (uint8_t)(value >> 24U);
}

bool TelemetryService_BuildMotion(const MotionFrame_t *motion,
                                  uint16_t sequence,
                                  ProtocolFrame_t *frame)
{
    size_t offset = 0U;
    const int32_t fields[8] = {motion != NULL ? motion->filtered.accel_mg_x : 0,
                               motion != NULL ? motion->filtered.accel_mg_y : 0,
                               motion != NULL ? motion->filtered.accel_mg_z : 0,
                               motion != NULL ? motion->filtered.gyro_mdps_x : 0,
                               motion != NULL ? motion->filtered.gyro_mdps_y : 0,
                               motion != NULL ? motion->filtered.gyro_mdps_z : 0,
                               motion != NULL ? motion->attitude.roll_cdeg : 0,
                               motion != NULL ? motion->attitude.pitch_cdeg : 0};
    uint32_t index;

    if ((motion == NULL) || (frame == NULL) || !motion->valid)
    {
        return false;
    }
    *frame = (ProtocolFrame_t){0};
    frame->version = PROTOCOL_VERSION;
    frame->type = PROTOCOL_TYPE_MOTION_TELEMETRY;
    frame->sequence = sequence;
    Put32(&frame->payload[offset], motion->timestamp_ms);
    offset += 4U;
    Put32(&frame->payload[offset], motion->sequence);
    offset += 4U;
    Put32(&frame->payload[offset], motion->status_flags);
    offset += 4U;
    frame->payload[offset++] = motion->calibrated ? 1U : 0U;
    for (index = 0U; index < 8U; ++index)
    {
        Put32(&frame->payload[offset], (uint32_t)fields[index]);
        offset += 4U;
    }
    frame->payload_length = (uint16_t)offset;
    return offset == TELEMETRY_MOTION_PAYLOAD_SIZE;
}

bool TelemetryService_BuildHealth(const HealthSnapshot_t *health,
                                  MotionServiceState_t motion_state,
                                  const MotionServiceStats_t *motion_stats,
                                  const TelemetryProtocolStats_t *protocol_stats,
                                  uint16_t sequence,
                                  ProtocolFrame_t *frame)
{
    size_t offset = 0U;

    if ((health == NULL) || (motion_stats == NULL) ||
        (protocol_stats == NULL) || (frame == NULL))
    {
        return false;
    }
    *frame = (ProtocolFrame_t){0};
    frame->version = PROTOCOL_VERSION;
    frame->type = PROTOCOL_TYPE_HEALTH_TELEMETRY;
    frame->sequence = sequence;
    Put32(&frame->payload[offset], health->uptime_ms);
    offset += 4U;
    frame->payload[offset++] = (uint8_t)health->app_state;
    frame->payload[offset++] = (uint8_t)motion_state;
    Put32(&frame->payload[offset], health->loop_count);
    offset += 4U;
    Put32(&frame->payload[offset], protocol_stats->i2c_error_count);
    offset += 4U;
    Put32(&frame->payload[offset], motion_stats->invalid_samples);
    offset += 4U;
    Put32(&frame->payload[offset], protocol_stats->protocol_rx_frames);
    offset += 4U;
    Put32(&frame->payload[offset], protocol_stats->protocol_crc_errors);
    offset += 4U;
    Put32(&frame->payload[offset], protocol_stats->rx_overflow_count);
    offset += 4U;
    frame->payload_length = (uint16_t)offset;
    return offset == TELEMETRY_HEALTH_PAYLOAD_SIZE;
}
