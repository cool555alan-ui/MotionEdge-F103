#ifndef RTOS_TASKS_H
#define RTOS_TASKS_H

#include <stdbool.h>

#include "protocol_frame.h"

#define RTOS_SENSOR_PERIOD_MS 10U
#define RTOS_COMMUNICATION_PERIOD_MS 2U
#define RTOS_TELEMETRY_PERIOD_MS 100U
#define RTOS_HEALTH_PERIOD_MS 1000U

#define RTOS_SENSOR_STACK_BYTES 1280U
#define RTOS_COMMUNICATION_STACK_BYTES 1024U
#define RTOS_TELEMETRY_STACK_BYTES 1024U
#define RTOS_HEALTH_STACK_BYTES 1280U
#define RTOS_TOTAL_APPLICATION_STACK_BYTES 4608U

bool RtosTasks_Create(void);
/** Parser生产者调用；只投递固定大小命令，不直接修改业务状态。 */
bool RtosTasks_QueueCommand(const ProtocolFrame_t *request);

#endif /* RTOS_TASKS_H */
