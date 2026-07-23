#include "health_service.h"

#include <stddef.h>

static bool s_initialized = false;
static uint32_t s_start_ms = 0U;
static uint32_t s_current_ms = 0U;
static uint32_t s_loop_count = 0U;
static uint32_t s_heartbeat_count = 0U;
static uint32_t s_log_failure_count = 0U;

void HealthService_Init(uint32_t now_ms)
{
    s_start_ms = now_ms;
    s_current_ms = now_ms;
    s_loop_count = 0U;
    s_heartbeat_count = 0U;
    s_log_failure_count = 0U;
    s_initialized = true;
}

void HealthService_RecordLoop(uint32_t now_ms)
{
    if (!s_initialized)
    {
        return;
    }

    s_current_ms = now_ms;
    ++s_loop_count;
}

void HealthService_RecordHeartbeat(void)
{
    if (s_initialized)
    {
        ++s_heartbeat_count;
    }
}

void HealthService_RecordLogFailure(void)
{
    if (s_initialized)
    {
        ++s_log_failure_count;
    }
}

bool HealthService_GetSnapshot(HealthSnapshot_t *snapshot)
{
    if ((snapshot == NULL) || !s_initialized)
    {
        return false;
    }

    snapshot->uptime_ms = s_current_ms - s_start_ms;
    snapshot->loop_count = s_loop_count;
    snapshot->heartbeat_count = s_heartbeat_count;
    snapshot->log_failure_count = s_log_failure_count;
    snapshot->app_state = AppStatus_GetState();
    return true;
}
