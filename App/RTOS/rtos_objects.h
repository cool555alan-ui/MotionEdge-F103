#ifndef RTOS_OBJECTS_H
#define RTOS_OBJECTS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "motion_service.h"
#include "protocol_frame.h"

#define RTOS_COMMAND_QUEUE_CAPACITY 8U
#define RTOS_COMMAND_MAX_PAYLOAD_SIZE 10U

#define RTOS_EVENT_SYSTEM_READY (1UL << 0)
#define RTOS_EVENT_SENSOR_ONLINE (1UL << 1)
#define RTOS_EVENT_CALIBRATED (1UL << 2)
#define RTOS_EVENT_TELEMETRY_ENABLED (1UL << 3)
#define RTOS_EVENT_PROTOCOL_MODE (1UL << 4)
#define RTOS_EVENT_DEGRADED (1UL << 5)
#define RTOS_EVENT_FAULT (1UL << 6)

typedef struct
{
    uint8_t version;
    uint8_t type;
    uint8_t flags;
    uint16_t sequence;
    uint16_t payload_length;
    uint8_t payload[RTOS_COMMAND_MAX_PAYLOAD_SIZE];
} RtosCommand_t;

bool RtosObjects_Init(void);
bool RtosObjects_PublishMotion(const MotionFrame_t *frame);
bool RtosObjects_GetMotionSnapshot(MotionFrame_t *frame);
bool RtosObjects_EnqueueCommand(const ProtocolFrame_t *request);
bool RtosObjects_TryDequeueCommand(RtosCommand_t *command);
uint32_t RtosObjects_GetCommandQueueCount(void);
bool RtosObjects_UartWrite(const uint8_t *data, size_t length);
bool RtosObjects_LoggerLock(void);
void RtosObjects_LoggerUnlock(void);
void RtosObjects_EnterCritical(void);
void RtosObjects_ExitCritical(void);
uint32_t RtosObjects_GetEvents(void);
bool RtosObjects_UpdateEvents(uint32_t set_bits, uint32_t clear_bits);

#endif /* RTOS_OBJECTS_H */
