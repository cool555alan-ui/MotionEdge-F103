#include "app_rtos.h"

#include "app_main.h"
#include "app_status.h"
#include "communication_service.h"
#include "config_service.h"
#include "logger.h"
#include "rtos_monitor.h"
#include "rtos_objects.h"
#include "rtos_tasks.h"

static bool s_initialized;

bool AppRtos_Init(void)
{
    s_initialized = false;
    RtosMonitor_Init();
    if (!RtosObjects_Init())
    {
        AppRtos_HandleFatalError();
        return false;
    }
    App_SetUartWriter(RtosObjects_UartWrite);
    if (!Logger_SetLock(RtosObjects_LoggerLock, RtosObjects_LoggerUnlock) ||
        !ConfigService_SetCriticalSection(RtosObjects_EnterCritical,
                                          RtosObjects_ExitCritical))
    {
        AppRtos_HandleFatalError();
        return false;
    }
    CommunicationService_SetCommandSink(RtosTasks_QueueCommand);
    if (!RtosTasks_Create())
    {
        AppRtos_HandleFatalError();
        return false;
    }
    if (!RtosObjects_UpdateEvents(RTOS_EVENT_SYSTEM_READY, RTOS_EVENT_FAULT))
    {
        AppRtos_HandleFatalError();
        return false;
    }
    s_initialized = true;
    return true;
}

bool AppRtos_IsInitialized(void)
{
    return s_initialized;
}

void AppRtos_HandleFatalError(void)
{
    s_initialized = false;
    (void)AppStatus_SetState(APP_STATE_FAULT);
    (void)RtosObjects_UpdateEvents(RTOS_EVENT_FAULT, RTOS_EVENT_SYSTEM_READY);
}
