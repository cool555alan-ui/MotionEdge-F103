#include "rtos_monitor.h"

#include <stddef.h>

static RtosMonitorSnapshot_t s_snapshot;

static uint32_t AbsTickDifference(uint32_t left, uint32_t right)
{
    int32_t difference = (int32_t)(left - right);
    return (difference < 0) ? (uint32_t)(-(int64_t)difference)
                            : (uint32_t)difference;
}

void RtosMonitor_Init(void)
{
    s_snapshot = (RtosMonitorSnapshot_t){0};
}

bool RtosMonitor_IsDeadlineMiss(uint32_t expected_ms,
                                uint32_t start_ms,
                                uint32_t end_ms,
                                uint32_t period_ms)
{
    uint32_t execution_ms;
    uint32_t lateness_ms;

    if (period_ms == 0U)
    {
        return true;
    }
    execution_ms = end_ms - start_ms;
    lateness_ms = ((int32_t)(start_ms - expected_ms) > 0)
                      ? (start_ms - expected_ms)
                      : 0U;
    return (execution_ms >= period_ms) || (lateness_ms >= period_ms);
}

bool RtosMonitor_IsStackWarning(uint32_t remaining_bytes,
                               uint32_t warning_threshold_bytes)
{
    return remaining_bytes < warning_threshold_bytes;
}

void RtosMonitor_RecordRun(RtosTaskId_t task,
                           uint32_t expected_ms,
                           uint32_t start_ms,
                           uint32_t end_ms,
                           uint32_t period_ms)
{
    RtosTaskStats_t *stats;
    uint32_t execution_us;
    uint32_t jitter_us;

    if (task >= RTOS_TASK_COUNT)
    {
        return;
    }
    stats = &s_snapshot.tasks[task];
    ++stats->run_count;
    stats->last_heartbeat_ms = start_ms;
    execution_us = (end_ms - start_ms) * 1000U;
    jitter_us = AbsTickDifference(start_ms, expected_ms) * 1000U;
    if (execution_us > stats->max_execution_us)
    {
        stats->max_execution_us = execution_us;
    }
    if (jitter_us > stats->max_jitter_us)
    {
        stats->max_jitter_us = jitter_us;
    }
    if (RtosMonitor_IsDeadlineMiss(expected_ms, start_ms, end_ms, period_ms))
    {
        ++stats->deadline_miss_count;
    }
}

void RtosMonitor_UpdateStack(RtosTaskId_t task, uint32_t remaining_bytes)
{
    if (task < RTOS_TASK_COUNT)
    {
        s_snapshot.tasks[task].stack_high_water_mark = remaining_bytes;
    }
}

void RtosMonitor_RecordQueueDepth(uint32_t depth)
{
    if (depth > s_snapshot.command_queue_high_water_mark)
    {
        s_snapshot.command_queue_high_water_mark = depth;
    }
}

void RtosMonitor_RecordQueueFull(void)
{
    ++s_snapshot.command_queue_full_count;
}

void RtosMonitor_RecordUartMutexTimeout(void)
{
    ++s_snapshot.uart_mutex_timeout_count;
}

void RtosMonitor_RecordSnapshotMutexTimeout(void)
{
    ++s_snapshot.snapshot_mutex_timeout_count;
}

void RtosMonitor_RecordLoggerMutexTimeout(void)
{
    ++s_snapshot.logger_mutex_timeout_count;
}

void RtosMonitor_RecordStackOverflow(void)
{
    ++s_snapshot.stack_overflow_count;
}

void RtosMonitor_RecordMallocFailure(void)
{
    ++s_snapshot.malloc_failure_count;
}

void RtosMonitor_UpdateHeap(uint32_t free_bytes, uint32_t minimum_ever_bytes)
{
    s_snapshot.free_heap_bytes = free_bytes;
    s_snapshot.minimum_ever_free_heap_bytes = minimum_ever_bytes;
}

bool RtosMonitor_GetSnapshot(RtosMonitorSnapshot_t *snapshot)
{
    if (snapshot == NULL)
    {
        return false;
    }
    *snapshot = s_snapshot;
    return true;
}

bool RtosMonitor_AllCriticalTasksAlive(uint32_t now_ms)
{
    static const uint32_t maximum_age_ms[RTOS_TASK_COUNT] = {
        100U, 100U, 500U, 2500U};
    uint32_t index;

    for (index = 0U; index < RTOS_TASK_COUNT; ++index)
    {
        if ((s_snapshot.tasks[index].run_count == 0U) ||
            ((uint32_t)(now_ms - s_snapshot.tasks[index].last_heartbeat_ms) >
             maximum_age_ms[index]))
        {
            return false;
        }
    }
    return true;
}
