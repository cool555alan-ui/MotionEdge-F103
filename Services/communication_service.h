#ifndef COMMUNICATION_SERVICE_H
#define COMMUNICATION_SERVICE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "motion_service.h"
#include "protocol_frame.h"

typedef bool (*CommunicationWriter_t)(const uint8_t *data, size_t length);
typedef bool (*CommunicationCommandSink_t)(const ProtocolFrame_t *request);

typedef struct
{
    uint32_t rx_overflow_count;
    uint32_t successful_frames;
    uint32_t crc_error_count;
    uint32_t parser_error_count;
    uint32_t command_error_count;
    uint32_t tx_error_count;
} CommunicationServiceStats_t;

/** 初始化固定RX缓冲、Parser、命令服务和遥测序号。 */
bool CommunicationService_Init(uint32_t now_ms);
/** 注入统一UART发送入口；NULL恢复为裸机BSP直写。 */
void CommunicationService_SetWriter(CommunicationWriter_t writer);
/** 注入已校验帧的任务间投递入口；NULL时保持裸机直接分发。 */
void CommunicationService_SetCommandSink(CommunicationCommandSink_t sink);
/** 按固定字节预算处理UART接收、命令响应和二进制遥测。 */
void CommunicationService_RunOnce(uint32_t now_ms);
/** 仅执行有界UART接收和协议解析。 */
void CommunicationService_RunRxOnce(void);
/** 在命令所有者任务中处理并发送一个完整请求。 */
bool CommunicationService_ProcessCommand(const ProtocolFrame_t *request);
/** 使用调用方提供的一致运动快照发送到期的二进制遥测。 */
void CommunicationService_RunTelemetry(uint32_t now_ms,
                                       const MotionFrame_t *motion);
bool CommunicationService_IsProtocolMode(void);
bool CommunicationService_GetStats(CommunicationServiceStats_t *stats);

#endif /* COMMUNICATION_SERVICE_H */
