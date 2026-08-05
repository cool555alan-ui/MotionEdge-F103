#include "rtos_objects.h"

#include <stddef.h>

#include "FreeRTOS.h"
#include "bsp_uart.h"
#include "cmsis_os2.h"
#include "event_groups.h"
#include "queue.h"
#include "rtos_monitor.h"
#include "semphr.h"

#define RTOS_SNAPSHOT_LOCK_TIMEOUT_MS 2U
#define RTOS_UART_LOCK_TIMEOUT_MS 25U

static StaticSemaphore_t s_motion_mutex_cb;
static StaticSemaphore_t s_uart_mutex_cb;
static StaticSemaphore_t s_logger_mutex_cb;
static StaticQueue_t s_command_queue_cb;
static StaticEventGroup_t s_event_flags_cb;
static uint8_t s_command_queue_storage[RTOS_COMMAND_QUEUE_CAPACITY *
                                       sizeof(RtosCommand_t)];
static osMutexId_t s_motion_mutex;
static osMutexId_t s_uart_mutex;
static osMutexId_t s_logger_mutex;
static osMessageQueueId_t s_command_queue;
static osEventFlagsId_t s_event_flags;
static MotionFrame_t s_latest_motion;
static bool s_has_motion;

bool RtosObjects_Init(void)
{
    const osMutexAttr_t motion_mutex_attributes = {
        .name = "MotionSnapshot",
        .cb_mem = &s_motion_mutex_cb,
        .cb_size = sizeof(s_motion_mutex_cb)};
    const osMutexAttr_t uart_mutex_attributes = {
        .name = "UartTx",
        .cb_mem = &s_uart_mutex_cb,
        .cb_size = sizeof(s_uart_mutex_cb)};
    const osMutexAttr_t logger_mutex_attributes = {
        .name = "Logger",
        .cb_mem = &s_logger_mutex_cb,
        .cb_size = sizeof(s_logger_mutex_cb)};
    const osMessageQueueAttr_t command_queue_attributes = {
        .name = "CommandQueue",
        .cb_mem = &s_command_queue_cb,
        .cb_size = sizeof(s_command_queue_cb),
        .mq_mem = s_command_queue_storage,
        .mq_size = sizeof(s_command_queue_storage)};
    const osEventFlagsAttr_t event_attributes = {
        .name = "SystemEvents",
        .cb_mem = &s_event_flags_cb,
        .cb_size = sizeof(s_event_flags_cb)};

    s_latest_motion = (MotionFrame_t){0};
    s_has_motion = false;
    s_motion_mutex = osMutexNew(&motion_mutex_attributes);
    s_uart_mutex = osMutexNew(&uart_mutex_attributes);
    s_logger_mutex = osMutexNew(&logger_mutex_attributes);
    s_command_queue = osMessageQueueNew(RTOS_COMMAND_QUEUE_CAPACITY,
                                        sizeof(RtosCommand_t),
                                        &command_queue_attributes);
    s_event_flags = osEventFlagsNew(&event_attributes);
    return (s_motion_mutex != NULL) && (s_uart_mutex != NULL) &&
           (s_logger_mutex != NULL) &&
           (s_command_queue != NULL) && (s_event_flags != NULL);
}

bool RtosObjects_PublishMotion(const MotionFrame_t *frame)
{
    if ((frame == NULL) ||
        (osMutexAcquire(s_motion_mutex, RTOS_SNAPSHOT_LOCK_TIMEOUT_MS) != osOK))
    {
        RtosMonitor_RecordSnapshotMutexTimeout();
        return false;
    }
    /* 临界区只复制固定结构，禁止日志、UART和算法处理。 */
    s_latest_motion = *frame;
    s_has_motion = true;
    (void)osMutexRelease(s_motion_mutex);
    return true;
}

bool RtosObjects_GetMotionSnapshot(MotionFrame_t *frame)
{
    bool available;

    if ((frame == NULL) ||
        (osMutexAcquire(s_motion_mutex, RTOS_SNAPSHOT_LOCK_TIMEOUT_MS) != osOK))
    {
        RtosMonitor_RecordSnapshotMutexTimeout();
        return false;
    }
    available = s_has_motion;
    if (available)
    {
        *frame = s_latest_motion;
    }
    (void)osMutexRelease(s_motion_mutex);
    return available;
}

bool RtosObjects_EnqueueCommand(const ProtocolFrame_t *request)
{
    RtosCommand_t command = {0};
    uint32_t depth;
    uint16_t copy_length;
    uint16_t index;

    if ((request == NULL) || (s_command_queue == NULL))
    {
        return false;
    }
    command.version = request->version;
    command.type = request->type;
    command.flags = request->flags;
    command.sequence = request->sequence;
    command.payload_length = request->payload_length;
    copy_length = (request->payload_length < RTOS_COMMAND_MAX_PAYLOAD_SIZE)
                      ? request->payload_length
                      : RTOS_COMMAND_MAX_PAYLOAD_SIZE;
    for (index = 0U; index < copy_length; ++index)
    {
        command.payload[index] = request->payload[index];
    }
    if (osMessageQueuePut(s_command_queue, &command, 0U, 0U) != osOK)
    {
        RtosMonitor_RecordQueueFull();
        return false;
    }
    depth = osMessageQueueGetCount(s_command_queue);
    RtosMonitor_RecordQueueDepth(depth);
    return true;
}

bool RtosObjects_TryDequeueCommand(RtosCommand_t *command)
{
    return (command != NULL) && (s_command_queue != NULL) &&
           (osMessageQueueGet(s_command_queue, command, NULL, 0U) == osOK);
}

uint32_t RtosObjects_GetCommandQueueCount(void)
{
    return (s_command_queue != NULL) ? osMessageQueueGetCount(s_command_queue) : 0U;
}

bool RtosObjects_UartWrite(const uint8_t *data, size_t length)
{
    bool success;

    if ((data == NULL) && (length != 0U))
    {
        return false;
    }
    if ((s_uart_mutex == NULL) ||
        (osMutexAcquire(s_uart_mutex, RTOS_UART_LOCK_TIMEOUT_MS) != osOK))
    {
        RtosMonitor_RecordUartMutexTimeout();
        return false;
    }
    success = BspUart_Write(data, length) == BSP_UART_OK;
    (void)osMutexRelease(s_uart_mutex);
    return success;
}

bool RtosObjects_LoggerLock(void)
{
    if ((s_logger_mutex == NULL) ||
        (osMutexAcquire(s_logger_mutex, RTOS_UART_LOCK_TIMEOUT_MS) != osOK))
    {
        RtosMonitor_RecordLoggerMutexTimeout();
        return false;
    }
    return true;
}

void RtosObjects_LoggerUnlock(void)
{
    if (s_logger_mutex != NULL)
    {
        (void)osMutexRelease(s_logger_mutex);
    }
}

void RtosObjects_EnterCritical(void)
{
    taskENTER_CRITICAL();
}

void RtosObjects_ExitCritical(void)
{
    taskEXIT_CRITICAL();
}

uint32_t RtosObjects_GetEvents(void)
{
    uint32_t flags = osEventFlagsGet(s_event_flags);
    return ((int32_t)flags < 0) ? 0U : flags;
}

bool RtosObjects_UpdateEvents(uint32_t set_bits, uint32_t clear_bits)
{
    if (s_event_flags == NULL)
    {
        return false;
    }
    if ((clear_bits != 0U) &&
        ((int32_t)osEventFlagsClear(s_event_flags, clear_bits) < 0))
    {
        return false;
    }
    return (set_bits == 0U) ||
           ((int32_t)osEventFlagsSet(s_event_flags, set_bits) >= 0);
}
