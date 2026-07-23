#include "app_main.h"

#include <inttypes.h>

#include "app_config.h"
#include "app_status.h"
#include "app_version.h"
#include "bsp_led.h"
#include "bsp_uart.h"
#include "health_service.h"
#include "logger.h"
#include "software_timer.h"

static SoftwareTimer_t s_heartbeat_timer;
static SoftwareTimer_t s_health_report_timer;
static bool s_app_initialized = false;

static bool App_UartLogWriter(const uint8_t *data, size_t length)
{
    return BspUart_Write(data, length) == BSP_UART_OK;
}

static void App_RecordLogResult(bool result)
{
    if (!result)
    {
        HealthService_RecordLogFailure();
    }
}

static void App_LogStartupInformation(void)
{
    App_RecordLogResult(Logger_Write(LOG_LEVEL_INFO, "APP", APP_NAME " starting"));
    App_RecordLogResult(
        Logger_Write(LOG_LEVEL_INFO, "APP", "Firmware version: " APP_VERSION_STRING));
    App_RecordLogResult(Logger_Write(LOG_LEVEL_INFO, "APP", "Build type: " APP_BUILD_TYPE));
    App_RecordLogResult(
        Logger_WriteFormatted(LOG_LEVEL_INFO,
                              "APP",
                              "System state: %s",
                              AppStatus_ToString(AppStatus_GetState())));
    App_RecordLogResult(Logger_Write(LOG_LEVEL_INFO, "APP", "Hardware validation: pending"));
}

bool App_Init(uint32_t now_ms)
{
    s_app_initialized = false;
    AppStatus_Init();
    if (!AppStatus_SetState(APP_STATE_INITIALIZING))
    {
        return false;
    }
    if (BspLed_Init() != BSP_LED_OK)
    {
        (void)AppStatus_SetState(APP_STATE_FAULT);
        return false;
    }
    if (BspUart_Init() != BSP_UART_OK)
    {
        (void)AppStatus_SetState(APP_STATE_FAULT);
        return false;
    }
    if (!Logger_Init(App_UartLogWriter, LOG_LEVEL_INFO))
    {
        (void)AppStatus_SetState(APP_STATE_FAULT);
        return false;
    }
    if (!SoftwareTimer_Init(&s_heartbeat_timer, now_ms, APP_HEARTBEAT_PERIOD_MS) ||
        !SoftwareTimer_Init(&s_health_report_timer, now_ms, APP_HEALTH_REPORT_PERIOD_MS))
    {
        (void)AppStatus_SetState(APP_STATE_FAULT);
        return false;
    }

    HealthService_Init(now_ms);
    if (!AppStatus_SetState(APP_STATE_RUNNING))
    {
        return false;
    }

    s_app_initialized = true;
    App_LogStartupInformation();
    return true;
}

void App_RunOnce(uint32_t now_ms)
{
    HealthSnapshot_t snapshot;

    if (!s_app_initialized)
    {
        return;
    }

    HealthService_RecordLoop(now_ms);

    if (SoftwareTimer_IsDue(&s_heartbeat_timer, now_ms))
    {
        if (BspLed_Toggle() == BSP_LED_OK)
        {
            HealthService_RecordHeartbeat();
        }
        else
        {
            (void)AppStatus_SetState(APP_STATE_DEGRADED);
        }
    }

    if (SoftwareTimer_IsDue(&s_health_report_timer, now_ms) &&
        HealthService_GetSnapshot(&snapshot))
    {
        App_RecordLogResult(
            Logger_WriteFormatted(LOG_LEVEL_INFO,
                                  "HEALTH",
                                  "uptime_ms=%" PRIu32 " loops=%" PRIu32
                                  " heartbeats=%" PRIu32 " state=%s log_errors=%" PRIu32,
                                  snapshot.uptime_ms,
                                  snapshot.loop_count,
                                  snapshot.heartbeat_count,
                                  AppStatus_ToString(snapshot.app_state),
                                  snapshot.log_failure_count));
    }
}
