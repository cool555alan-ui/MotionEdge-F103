#include "rtos_monitor.h"
#include "rtos_objects.h"
#include "rtos_tasks.h"
#include "test_support.h"

void TestRtosMonitor_Run(TestContext_t *context)
{
    RtosMonitorSnapshot_t snapshot;
    RtosCommand_t command = {0};
    uint32_t task;

    TEST_EXPECT(context, RTOS_SENSOR_PERIOD_MS == 10U);
    TEST_EXPECT(context, RTOS_COMMUNICATION_PERIOD_MS == 2U);
    TEST_EXPECT(context, RTOS_TELEMETRY_PERIOD_MS == 100U);
    TEST_EXPECT(context, RTOS_HEALTH_PERIOD_MS == 1000U);
    TEST_EXPECT(context, RTOS_SENSOR_STACK_BYTES == 1280U);
    TEST_EXPECT(context, RTOS_COMMUNICATION_STACK_BYTES == 1024U);
    TEST_EXPECT(context, RTOS_TELEMETRY_STACK_BYTES == 1088U);
    TEST_EXPECT(context, RTOS_HEALTH_STACK_BYTES == 1280U);
    TEST_EXPECT(context, RTOS_TOTAL_APPLICATION_STACK_BYTES == 4672U);
    TEST_EXPECT(context, RTOS_COMMAND_QUEUE_CAPACITY == 8U);
    TEST_EXPECT(context, RTOS_COMMAND_MAX_PAYLOAD_SIZE == 20U);
    /* 8字节头部（含对齐）+ 20字节最长命令负载。 */
    TEST_EXPECT(context, sizeof(command) <= 28U);
    TEST_EXPECT(context,
                (RTOS_EVENT_SYSTEM_READY | RTOS_EVENT_SENSOR_ONLINE |
                 RTOS_EVENT_CALIBRATED | RTOS_EVENT_TELEMETRY_ENABLED |
                 RTOS_EVENT_PROTOCOL_MODE | RTOS_EVENT_DEGRADED |
                 RTOS_EVENT_FAULT) == 0x7FU);

    RtosMonitor_Init();
    TEST_EXPECT(context, RtosMonitor_GetSnapshot(&snapshot));
    TEST_EXPECT(context, !RtosMonitor_AllCriticalTasksAlive(100U));
    TEST_EXPECT(context, !RtosMonitor_IsDeadlineMiss(100U, 102U, 104U, 10U));
    TEST_EXPECT(context, RtosMonitor_IsDeadlineMiss(100U, 110U, 111U, 10U));
    TEST_EXPECT(context, RtosMonitor_IsDeadlineMiss(100U, 100U, 110U, 10U));
    TEST_EXPECT(context, RtosMonitor_IsStackWarning(127U, 128U));
    TEST_EXPECT(context, !RtosMonitor_IsStackWarning(128U, 128U));

    for (task = 0U; task < RTOS_TASK_COUNT; ++task)
    {
        RtosMonitor_RecordRun((RtosTaskId_t)task, 100U, 102U, 104U, 10U);
        RtosMonitor_UpdateStack((RtosTaskId_t)task, 256U);
    }
    RtosMonitor_RecordQueueDepth(3U);
    RtosMonitor_RecordQueueDepth(2U);
    RtosMonitor_RecordQueueFull();
    RtosMonitor_RecordUartMutexTimeout();
    RtosMonitor_RecordSnapshotMutexTimeout();
    RtosMonitor_RecordLoggerMutexTimeout();
    RtosMonitor_UpdateHeap(2048U, 1536U);
    TEST_EXPECT(context, RtosMonitor_GetSnapshot(&snapshot));
    TEST_EXPECT(context, snapshot.tasks[RTOS_TASK_SENSOR].run_count == 1U);
    TEST_EXPECT(context, snapshot.tasks[RTOS_TASK_SENSOR].max_jitter_us == 2000U);
    TEST_EXPECT(context, snapshot.tasks[RTOS_TASK_SENSOR].max_execution_us == 2000U);
    TEST_EXPECT(context, snapshot.tasks[RTOS_TASK_SENSOR].stack_high_water_mark == 256U);
    TEST_EXPECT(context, snapshot.command_queue_high_water_mark == 3U);
    TEST_EXPECT(context, snapshot.command_queue_full_count == 1U);
    TEST_EXPECT(context, snapshot.uart_mutex_timeout_count == 1U);
    TEST_EXPECT(context, snapshot.snapshot_mutex_timeout_count == 1U);
    TEST_EXPECT(context, snapshot.logger_mutex_timeout_count == 1U);
    TEST_EXPECT(context, snapshot.free_heap_bytes == 2048U);
    TEST_EXPECT(context, snapshot.minimum_ever_free_heap_bytes == 1536U);
    TEST_EXPECT(context, RtosMonitor_AllCriticalTasksAlive(104U));
    TEST_EXPECT(context, !RtosMonitor_AllCriticalTasksAlive(3000U));
}
