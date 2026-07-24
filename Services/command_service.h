#ifndef COMMAND_SERVICE_H
#define COMMAND_SERVICE_H

#include <stdbool.h>

#include "protocol_frame.h"

typedef enum
{
    COMMAND_SERVICE_MODE_DEVELOPMENT = 0,
    COMMAND_SERVICE_MODE_PROTOCOL
} CommandServiceMode_t;

/** 初始化命令分发与开发模式状态。 */
bool CommandService_Init(void);
/** 校验请求并构造相同sequence的统一响应。 */
bool CommandService_Process(const ProtocolFrame_t *request,
                            ProtocolFrame_t *response);
CommandServiceMode_t CommandService_GetMode(void);
/** 协议模式下禁止普通日志和CSV混入二进制流。 */
bool CommandService_IsProtocolMode(void);

#endif /* COMMAND_SERVICE_H */
