#ifndef RTOS_MONITOR_H
#define RTOS_MONITOR_H

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    RTOS_TASK_SENSOR = 0,
    RTOS_TASK_COMMUNICATION,
    RTOS_TASK_TELEMETRY,
    RTOS_TASK_HEALTH,
    RTOS_TASK_COUNT
} RtosTaskId_t;

typedef struct
{
    uint32_t run_count;
    uint32_t deadline_miss_count;
    uint32_t max_execution_us;
    uint32_t max_jitter_us;
    uint32_t last_heartbeat_ms;
    uint32_t stack_high_water_mark;
} RtosTaskStats_t;

typedef struct
{
    RtosTaskStats_t tasks[RTOS_TASK_COUNT];
    uint32_t command_queue_high_water_mark;
    uint32_t command_queue_full_count;
    uint32_t uart_mutex_timeout_count;
    uint32_t snapshot_mutex_timeout_count;
    uint32_t logger_mutex_timeout_count;
    uint32_t stack_overflow_count;
    uint32_t malloc_failure_count;
    uint32_t free_heap_bytes;
    uint32_t minimum_ever_free_heap_bytes;
} RtosMonitorSnapshot_t;

void RtosMonitor_Init(void);
void RtosMonitor_RecordRun(RtosTaskId_t task,
                           uint32_t expected_ms,
                           uint32_t start_ms,
                           uint32_t end_ms,
                           uint32_t period_ms);
void RtosMonitor_UpdateStack(RtosTaskId_t task, uint32_t remaining_bytes);
void RtosMonitor_RecordQueueDepth(uint32_t depth);
void RtosMonitor_RecordQueueFull(void);
void RtosMonitor_RecordUartMutexTimeout(void);
void RtosMonitor_RecordSnapshotMutexTimeout(void);
void RtosMonitor_RecordLoggerMutexTimeout(void);
/** 记录FreeRTOS栈溢出钩子触发次数。 */
void RtosMonitor_RecordStackOverflow(void);
/** 记录FreeRTOS内存分配失败钩子触发次数。 */
void RtosMonitor_RecordMallocFailure(void);
void RtosMonitor_UpdateHeap(uint32_t free_bytes, uint32_t minimum_ever_bytes);
bool RtosMonitor_GetSnapshot(RtosMonitorSnapshot_t *snapshot);
bool RtosMonitor_AllCriticalTasksAlive(uint32_t now_ms);

/** 使用32位回绕安全差值判断任务是否错过本周期截止时间。 */
bool RtosMonitor_IsDeadlineMiss(uint32_t expected_ms,
                                uint32_t start_ms,
                                uint32_t end_ms,
                                uint32_t period_ms);
bool RtosMonitor_IsStackWarning(uint32_t remaining_bytes,
                               uint32_t warning_threshold_bytes);

#endif /* RTOS_MONITOR_H */
