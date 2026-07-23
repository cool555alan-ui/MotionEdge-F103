#ifndef APP_STATUS_H
#define APP_STATUS_H

#include <stdbool.h>

typedef enum
{
    APP_STATE_BOOT = 0,
    APP_STATE_INITIALIZING,
    APP_STATE_RUNNING,
    APP_STATE_DEGRADED,
    APP_STATE_FAULT
} AppState_t;

void AppStatus_Init(void);
bool AppStatus_SetState(AppState_t new_state);
AppState_t AppStatus_GetState(void);
const char *AppStatus_ToString(AppState_t state);

#endif /* APP_STATUS_H */
