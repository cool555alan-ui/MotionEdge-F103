#include "rtos_tasks.h"

#include <inttypes.h>
#include <stddef.h>

#include "FreeRTOS.h"
#include "app_main.h"
#include "app_status.h"
#include "cmsis_os2.h"
#include "communication_service.h"
#include "config_service.h"
#include "logger.h"
#include "motion_service.h"
#include "rtos_monitor.h"
#include "rtos_objects.h"
#include "task.h"

#define RTOS_STACK_WARNING_BYTES 128U
#define RTOS_HEALTH_WARMUP_MS 3000U

static StaticTask_t s_sensor_task_cb;
static StaticTask_t s_communication_task_cb;
static StaticTask_t s_telemetry_task_cb;
static StaticTask_t s_health_task_cb;
static StackType_t s_sensor_stack[RTOS_SENSOR_STACK_BYTES / sizeof(StackType_t)];
static StackType_t s_communication_stack[RTOS_COMMUNICATION_STACK_BYTES /
                                         sizeof(StackType_t)];
static StackType_t s_telemetry_stack[RTOS_TELEMETRY_STACK_BYTES /
                                     sizeof(StackType_t)];
static StackType_t s_health_stack[RTOS_HEALTH_STACK_BYTES / sizeof(StackType_t)];
static osThreadId_t s_sensor_task;
static osThreadId_t s_communication_task;
static osThreadId_t s_telemetry_task;
static osThreadId_t s_health_task;

static void RecordTaskRun(RtosTaskId_t task,
                          uint32_t expected,
                          uint32_t start,
                          uint32_t period)
{
    RtosMonitor_RecordRun(task, expected, start, osKernelGetTickCount(), period);
}

static void UpdateSystemEvents(const MotionFrame_t *frame)
{
    uint32_t set_bits = RTOS_EVENT_SYSTEM_READY;
    uint32_t clear_bits = 0U;
    RuntimeConfig_t config;
    MotionServiceState_t motion_state = MotionService_GetState();
    AppState_t app_state = AppStatus_GetState();

    if ((motion_state == MOTION_SERVICE_STATE_CALIBRATING) ||
        (motion_state == MOTION_SERVICE_STATE_RUNNING))
    {
        set_bits |= RTOS_EVENT_SENSOR_ONLINE;
    }
    else
    {
        clear_bits |= RTOS_EVENT_SENSOR_ONLINE;
    }
    if ((frame != NULL) && frame->calibrated)
    {
        set_bits |= RTOS_EVENT_CALIBRATED;
    }
    else
    {
        clear_bits |= RTOS_EVENT_CALIBRATED;
    }
    if (ConfigService_Get(&config) && config.telemetry_enabled)
    {
        set_bits |= RTOS_EVENT_TELEMETRY_ENABLED | RTOS_EVENT_PROTOCOL_MODE;
    }
    else
    {
        clear_bits |= RTOS_EVENT_TELEMETRY_ENABLED | RTOS_EVENT_PROTOCOL_MODE;
    }
    if ((app_state == APP_STATE_DEGRADED) ||
        (motion_state == MOTION_SERVICE_STATE_DEGRADED))
    {
        set_bits |= RTOS_EVENT_DEGRADED;
    }
    else
    {
        clear_bits |= RTOS_EVENT_DEGRADED;
    }
    if (app_state == APP_STATE_FAULT)
    {
        set_bits |= RTOS_EVENT_FAULT;
    }
    (void)RtosObjects_UpdateEvents(set_bits, clear_bits);
}

static void SensorTask(void *argument)
{
    uint32_t expected = osKernelGetTickCount();
    uint32_t last_published_sequence = 0U;
    bool has_published = false;
    (void)argument;

    for (;;)
    {
        MotionFrame_t frame;
        RtosCommand_t command;
        uint32_t start = osKernelGetTickCount();
        bool got_frame;

        App_SensorRunOnce(start);
        if (RtosObjects_TryDequeueCommand(&command))
        {
            ProtocolFrame_t request = {0};
            uint16_t copy_length =
                (command.payload_length < RTOS_COMMAND_MAX_PAYLOAD_SIZE)
                    ? command.payload_length
                    : RTOS_COMMAND_MAX_PAYLOAD_SIZE;
            uint16_t index;
            request.version = command.version;
            request.type = command.type;
            request.flags = command.flags;
            request.sequence = command.sequence;
            request.payload_length = command.payload_length;
            for (index = 0U; index < copy_length; ++index)
            {
                request.payload[index] = command.payload[index];
            }
            (void)App_ProcessCommand(&request);
        }
        got_frame = MotionService_GetLatestFrame(&frame);
        if (got_frame &&
            (!has_published || (frame.sequence != last_published_sequence)))
        {
            if (RtosObjects_PublishMotion(&frame))
            {
                last_published_sequence = frame.sequence;
                has_published = true;
            }
        }
        UpdateSystemEvents(got_frame ? &frame : NULL);
        RecordTaskRun(RTOS_TASK_SENSOR, expected, start, RTOS_SENSOR_PERIOD_MS);
        expected += RTOS_SENSOR_PERIOD_MS;
        (void)osDelayUntil(expected);
    }
}

static void CommunicationTask(void *argument)
{
    uint32_t expected = osKernelGetTickCount();
    (void)argument;

    for (;;)
    {
        uint32_t start = osKernelGetTickCount();
        App_CommunicationRunOnce(start);
        RecordTaskRun(RTOS_TASK_COMMUNICATION,
                      expected,
                      start,
                      RTOS_COMMUNICATION_PERIOD_MS);
        expected += RTOS_COMMUNICATION_PERIOD_MS;
        (void)osDelayUntil(expected);
    }
}

static void TelemetryTask(void *argument)
{
    uint32_t expected = osKernelGetTickCount();
    uint32_t last_sequence = 0U;
    bool has_sequence = false;
    (void)argument;

    for (;;)
    {
        MotionFrame_t frame;
        uint32_t start = osKernelGetTickCount();
        const MotionFrame_t *snapshot = NULL;

        if (RtosObjects_GetMotionSnapshot(&frame) &&
            (!has_sequence || (frame.sequence != last_sequence)))
        {
            snapshot = &frame;
            last_sequence = frame.sequence;
            has_sequence = true;
        }
        App_TelemetryRunOnce(start, snapshot);
        RecordTaskRun(RTOS_TASK_TELEMETRY,
                      expected,
                      start,
                      RTOS_TELEMETRY_PERIOD_MS);
        expected += RTOS_TELEMETRY_PERIOD_MS;
        (void)osDelayUntil(expected);
    }
}

static void UpdateStackHighWaterMarks(void)
{
    RtosMonitor_UpdateStack(
        RTOS_TASK_SENSOR,
        (uint32_t)uxTaskGetStackHighWaterMark((TaskHandle_t)s_sensor_task) *
            sizeof(StackType_t));
    RtosMonitor_UpdateStack(
        RTOS_TASK_COMMUNICATION,
        (uint32_t)uxTaskGetStackHighWaterMark((TaskHandle_t)s_communication_task) *
            sizeof(StackType_t));
    RtosMonitor_UpdateStack(
        RTOS_TASK_TELEMETRY,
        (uint32_t)uxTaskGetStackHighWaterMark((TaskHandle_t)s_telemetry_task) *
            sizeof(StackType_t));
    RtosMonitor_UpdateStack(
        RTOS_TASK_HEALTH,
        (uint32_t)uxTaskGetStackHighWaterMark((TaskHandle_t)s_health_task) *
            sizeof(StackType_t));
}

static bool HasStackWarning(const RtosMonitorSnapshot_t *snapshot)
{
    uint32_t index;
    if (snapshot == NULL)
    {
        return true;
    }
    for (index = 0U; index < RTOS_TASK_COUNT; ++index)
    {
        if (RtosMonitor_IsStackWarning(
                snapshot->tasks[index].stack_high_water_mark,
                RTOS_STACK_WARNING_BYTES))
        {
            return true;
        }
    }
    return false;
}

static void HealthTask(void *argument)
{
    uint32_t expected = osKernelGetTickCount();
    (void)argument;

    for (;;)
    {
        RtosMonitorSnapshot_t snapshot;
        CommunicationServiceStats_t communication_stats;
        uint32_t start = osKernelGetTickCount();

        App_HealthRunOnce(start);
        UpdateStackHighWaterMarks();
        RtosMonitor_UpdateHeap((uint32_t)xPortGetFreeHeapSize(),
                               (uint32_t)xPortGetMinimumEverFreeHeapSize());
        if (RtosMonitor_GetSnapshot(&snapshot))
        {
            if ((start > RTOS_HEALTH_WARMUP_MS) &&
                (!RtosMonitor_AllCriticalTasksAlive(start) ||
                 HasStackWarning(&snapshot)))
            {
                (void)AppStatus_SetState(APP_STATE_DEGRADED);
                (void)RtosObjects_UpdateEvents(RTOS_EVENT_DEGRADED, 0U);
            }
            if (!CommunicationService_IsProtocolMode())
            {
                (void)Logger_WriteFormatted(
                    LOG_LEVEL_INFO,
                    "RTOS",
                    "kernel=%d run=%" PRIu32 "/%" PRIu32 "/%" PRIu32 "/%" PRIu32
                    ,
                    (int)osKernelGetState(),
                    snapshot.tasks[RTOS_TASK_SENSOR].run_count,
                    snapshot.tasks[RTOS_TASK_COMMUNICATION].run_count,
                    snapshot.tasks[RTOS_TASK_TELEMETRY].run_count,
                    snapshot.tasks[RTOS_TASK_HEALTH].run_count);
                /* 拆分统计日志，限制单次变参格式化的栈压力。 */
                (void)Logger_WriteFormatted(
                    LOG_LEVEL_INFO,
                    "RTOS-HB",
                    "hb=%" PRIu32 "/%" PRIu32 "/%" PRIu32 "/%" PRIu32,
                    snapshot.tasks[RTOS_TASK_SENSOR].last_heartbeat_ms,
                    snapshot.tasks[RTOS_TASK_COMMUNICATION].last_heartbeat_ms,
                    snapshot.tasks[RTOS_TASK_TELEMETRY].last_heartbeat_ms,
                    snapshot.tasks[RTOS_TASK_HEALTH].last_heartbeat_ms);
                (void)Logger_WriteFormatted(
                    LOG_LEVEL_INFO,
                    "RTOS-DEADLINE",
                    "miss=%" PRIu32 "/%" PRIu32 "/%" PRIu32 "/%" PRIu32
                    " heap=%" PRIu32 "/%" PRIu32,
                    snapshot.tasks[RTOS_TASK_SENSOR].deadline_miss_count,
                    snapshot.tasks[RTOS_TASK_COMMUNICATION].deadline_miss_count,
                    snapshot.tasks[RTOS_TASK_TELEMETRY].deadline_miss_count,
                    snapshot.tasks[RTOS_TASK_HEALTH].deadline_miss_count,
                    snapshot.free_heap_bytes,
                    snapshot.minimum_ever_free_heap_bytes);
                (void)Logger_WriteFormatted(
                    LOG_LEVEL_INFO,
                    "RTOS-MEM",
                    "stack_words=%" PRIu32 "/%" PRIu32 "/%" PRIu32 "/%" PRIu32
                    " unit=%uB",
                    snapshot.tasks[RTOS_TASK_SENSOR].stack_high_water_mark /
                        (uint32_t)sizeof(StackType_t),
                    snapshot.tasks[RTOS_TASK_COMMUNICATION].stack_high_water_mark /
                        (uint32_t)sizeof(StackType_t),
                    snapshot.tasks[RTOS_TASK_TELEMETRY].stack_high_water_mark /
                        (uint32_t)sizeof(StackType_t),
                    snapshot.tasks[RTOS_TASK_HEALTH].stack_high_water_mark /
                        (uint32_t)sizeof(StackType_t),
                    (unsigned int)sizeof(StackType_t));
                (void)Logger_WriteFormatted(
                    LOG_LEVEL_INFO,
                    "RTOS-MEM-BYTES",
                    "stack_bytes=%" PRIu32 "/%" PRIu32 "/%" PRIu32 "/%" PRIu32,
                    snapshot.tasks[RTOS_TASK_SENSOR].stack_high_water_mark,
                    snapshot.tasks[RTOS_TASK_COMMUNICATION].stack_high_water_mark,
                    snapshot.tasks[RTOS_TASK_TELEMETRY].stack_high_water_mark,
                    snapshot.tasks[RTOS_TASK_HEALTH].stack_high_water_mark);
                (void)Logger_WriteFormatted(
                    LOG_LEVEL_INFO,
                    "RTOS-IPC",
                    "q=%" PRIu32 "/%" PRIu32 "/%" PRIu32
                    " mutex=%" PRIu32 "/%" PRIu32 "/%" PRIu32,
                    RtosObjects_GetCommandQueueCount(),
                    snapshot.command_queue_high_water_mark,
                    snapshot.command_queue_full_count,
                    snapshot.uart_mutex_timeout_count,
                    snapshot.snapshot_mutex_timeout_count,
                    snapshot.logger_mutex_timeout_count);
                (void)Logger_WriteFormatted(
                    LOG_LEVEL_INFO,
                    "RTOS-FAIL",
                    "stack_overflow=%" PRIu32 " malloc_failure=%" PRIu32,
                    snapshot.stack_overflow_count,
                    snapshot.malloc_failure_count);
                (void)Logger_WriteFormatted(
                    LOG_LEVEL_INFO,
                    "RTOS-TIME",
                    "exec_us=%" PRIu32 "/%" PRIu32 "/%" PRIu32 "/%" PRIu32,
                    snapshot.tasks[RTOS_TASK_SENSOR].max_execution_us,
                    snapshot.tasks[RTOS_TASK_COMMUNICATION].max_execution_us,
                    snapshot.tasks[RTOS_TASK_TELEMETRY].max_execution_us,
                    snapshot.tasks[RTOS_TASK_HEALTH].max_execution_us);
                (void)Logger_WriteFormatted(
                    LOG_LEVEL_INFO,
                    "RTOS-JITTER",
                    "jitter_us=%" PRIu32 "/%" PRIu32 "/%" PRIu32 "/%" PRIu32,
                    snapshot.tasks[RTOS_TASK_SENSOR].max_jitter_us,
                    snapshot.tasks[RTOS_TASK_COMMUNICATION].max_jitter_us,
                    snapshot.tasks[RTOS_TASK_TELEMETRY].max_jitter_us,
                    snapshot.tasks[RTOS_TASK_HEALTH].max_jitter_us);
                if (CommunicationService_GetStats(&communication_stats))
                {
                    (void)Logger_WriteFormatted(
                        LOG_LEVEL_INFO,
                        "RTOS-COMM",
                        "rx=%" PRIu32 " crc=%" PRIu32 " parser=%" PRIu32
                        " command=%" PRIu32 " tx=%" PRIu32,
                        communication_stats.rx_overflow_count,
                        communication_stats.crc_error_count,
                        communication_stats.parser_error_count,
                        communication_stats.command_error_count,
                        communication_stats.tx_error_count);
                }
            }
        }
        RecordTaskRun(RTOS_TASK_HEALTH, expected, start, RTOS_HEALTH_PERIOD_MS);
        expected += RTOS_HEALTH_PERIOD_MS;
        (void)osDelayUntil(expected);
    }
}

bool RtosTasks_QueueCommand(const ProtocolFrame_t *request)
{
    return RtosObjects_EnqueueCommand(request);
}

bool RtosTasks_Create(void)
{
    const osThreadAttr_t sensor_attributes = {
        .name = "SensorTask",
        .cb_mem = &s_sensor_task_cb,
        .cb_size = sizeof(s_sensor_task_cb),
        .stack_mem = s_sensor_stack,
        .stack_size = sizeof(s_sensor_stack),
        .priority = osPriorityAboveNormal};
    const osThreadAttr_t communication_attributes = {
        .name = "CommunicationTask",
        .cb_mem = &s_communication_task_cb,
        .cb_size = sizeof(s_communication_task_cb),
        .stack_mem = s_communication_stack,
        .stack_size = sizeof(s_communication_stack),
        .priority = osPriorityAboveNormal};
    const osThreadAttr_t telemetry_attributes = {
        .name = "TelemetryTask",
        .cb_mem = &s_telemetry_task_cb,
        .cb_size = sizeof(s_telemetry_task_cb),
        .stack_mem = s_telemetry_stack,
        .stack_size = sizeof(s_telemetry_stack),
        .priority = osPriorityNormal};
    const osThreadAttr_t health_attributes = {
        .name = "HealthTask",
        .cb_mem = &s_health_task_cb,
        .cb_size = sizeof(s_health_task_cb),
        .stack_mem = s_health_stack,
        .stack_size = sizeof(s_health_stack),
        .priority = osPriorityLow};

    s_sensor_task = osThreadNew(SensorTask, NULL, &sensor_attributes);
    s_communication_task =
        osThreadNew(CommunicationTask, NULL, &communication_attributes);
    s_telemetry_task = osThreadNew(TelemetryTask, NULL, &telemetry_attributes);
    s_health_task = osThreadNew(HealthTask, NULL, &health_attributes);
    if ((s_sensor_task != NULL) && (s_communication_task != NULL) &&
        (s_telemetry_task != NULL) && (s_health_task != NULL))
    {
        return true;
    }
    /* 创建失败时回收已建立任务，避免以部分任务集合继续运行。 */
    if (s_sensor_task != NULL)
    {
        (void)osThreadTerminate(s_sensor_task);
        s_sensor_task = NULL;
    }
    if (s_communication_task != NULL)
    {
        (void)osThreadTerminate(s_communication_task);
        s_communication_task = NULL;
    }
    if (s_telemetry_task != NULL)
    {
        (void)osThreadTerminate(s_telemetry_task);
        s_telemetry_task = NULL;
    }
    if (s_health_task != NULL)
    {
        (void)osThreadTerminate(s_health_task);
        s_health_task = NULL;
    }
    return false;
}
