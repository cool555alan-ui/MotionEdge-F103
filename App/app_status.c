#include "app_status.h"

static AppState_t s_app_state = APP_STATE_BOOT;

void AppStatus_Init(void)
{
    s_app_state = APP_STATE_BOOT;
}

bool AppStatus_SetState(AppState_t new_state)
{
    if ((new_state < APP_STATE_BOOT) || (new_state > APP_STATE_FAULT))
    {
        return false;
    }

    s_app_state = new_state;
    return true;
}

AppState_t AppStatus_GetState(void)
{
    return s_app_state;
}

const char *AppStatus_ToString(AppState_t state)
{
    switch (state)
    {
        case APP_STATE_BOOT:
            return "BOOT";
        case APP_STATE_INITIALIZING:
            return "INITIALIZING";
        case APP_STATE_RUNNING:
            return "RUNNING";
        case APP_STATE_DEGRADED:
            return "DEGRADED";
        case APP_STATE_FAULT:
            return "FAULT";
        default:
            return "UNKNOWN";
    }
}
