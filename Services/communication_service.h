#ifndef COMMUNICATION_SERVICE_H
#define COMMUNICATION_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

/** 初始化固定RX缓冲、Parser、命令服务和遥测序号。 */
bool CommunicationService_Init(uint32_t now_ms);
/** 按固定字节预算处理UART接收、命令响应和二进制遥测。 */
void CommunicationService_RunOnce(uint32_t now_ms);
bool CommunicationService_IsProtocolMode(void);

#endif /* COMMUNICATION_SERVICE_H */
