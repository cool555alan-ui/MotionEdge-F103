#ifndef HEALTH_SERVICE_H
#define HEALTH_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

#include "app_status.h"

typedef struct
{
    uint32_t uptime_ms;
    uint32_t loop_count;
    uint32_t heartbeat_count;
    uint32_t log_failure_count;
    AppState_t app_state;
} HealthSnapshot_t;

void HealthService_Init(uint32_t now_ms);
void HealthService_RecordLoop(uint32_t now_ms);
void HealthService_RecordHeartbeat(void);
void HealthService_RecordLogFailure(void);
bool HealthService_GetSnapshot(HealthSnapshot_t *snapshot);

#endif /* HEALTH_SERVICE_H */
