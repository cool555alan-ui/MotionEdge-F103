#ifndef APP_MAIN_H
#define APP_MAIN_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "motion_service.h"
#include "protocol_frame.h"

typedef bool (*AppUartWriter_t)(const uint8_t *data, size_t length);

bool App_Init(uint32_t now_ms);
/** 注入统一UART发送入口；用于RTOS阶段串行化所有文本和二进制发送。 */
void App_SetUartWriter(AppUartWriter_t writer);
/** SensorTask调用：推进扫描、采样、校准、滤波及姿态状态机。 */
void App_SensorRunOnce(uint32_t now_ms);
/** CommunicationTask调用：执行有界串口接收和Parser。 */
void App_CommunicationRunOnce(uint32_t now_ms);
/** SensorTask调用：处理从固定命令队列取得的请求。 */
bool App_ProcessCommand(const ProtocolFrame_t *request);
/** TelemetryTask调用：仅使用传入的一致运动快照生成遥测。 */
void App_TelemetryRunOnce(uint32_t now_ms, const MotionFrame_t *frame);
/** HealthTask调用：心跳、状态和健康摘要。 */
void App_HealthRunOnce(uint32_t now_ms);
/** 裸机兼容入口；RTOS主运行路径不得调用。 */
void App_RunOnce(uint32_t now_ms);

#endif /* APP_MAIN_H */
