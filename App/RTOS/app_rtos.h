#ifndef APP_RTOS_H
#define APP_RTOS_H

#include <stdbool.h>

/** 创建全部静态RTOS对象与四个应用任务；任一失败即进入FAULT。 */
bool AppRtos_Init(void);
bool AppRtos_IsInitialized(void);
void AppRtos_HandleFatalError(void);

#endif /* APP_RTOS_H */
