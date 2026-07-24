#ifndef TELEMETRY_SERVICE_H
#define TELEMETRY_SERVICE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "health_service.h"
#include "motion_service.h"
#include "protocol_frame.h"

#define TELEMETRY_MOTION_PAYLOAD_SIZE 45U
#define TELEMETRY_HEALTH_PAYLOAD_SIZE 30U

typedef struct
{
    uint32_t i2c_error_count;
    uint32_t protocol_rx_frames;
    uint32_t protocol_crc_errors;
    uint32_t rx_overflow_count;
} TelemetryProtocolStats_t;

/** 逐字段小端序构造Motion遥测，避免结构体填充差异。 */
bool TelemetryService_BuildMotion(const MotionFrame_t *motion,
                                  uint16_t sequence,
                                  ProtocolFrame_t *frame);
/** 逐字段小端序构造Health遥测。 */
bool TelemetryService_BuildHealth(const HealthSnapshot_t *health,
                                  MotionServiceState_t motion_state,
                                  const MotionServiceStats_t *motion_stats,
                                  const TelemetryProtocolStats_t *protocol_stats,
                                  uint16_t sequence,
                                  ProtocolFrame_t *frame);

#endif /* TELEMETRY_SERVICE_H */
