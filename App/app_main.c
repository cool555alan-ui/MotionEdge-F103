#include "app_main.h"

#include <inttypes.h>

#include "app_config.h"
#include "app_status.h"
#include "app_version.h"
#include "bsp_i2c.h"
#include "bsp_led.h"
#include "bsp_uart.h"
#include "health_service.h"
#include "i2c_scanner.h"
#include "logger.h"
#include "mpu6050.h"
#include "software_timer.h"

static SoftwareTimer_t s_heartbeat_timer;
static SoftwareTimer_t s_health_report_timer;
static SoftwareTimer_t s_sensor_read_timer;
static I2cScanner_t s_i2c_scanner;
static Mpu6050_t s_mpu6050;
static bool s_app_initialized = false;
static bool s_sensor_ready = false;
static uint8_t s_mpu6050_address = 0U;

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

static bool App_I2cProbe(uint8_t address_7bit)
{
    return BspI2c_IsDeviceReady(address_7bit) == BSP_I2C_OK;
}

static bool App_Mpu6050Read(uint8_t address_7bit,
                           uint8_t register_address,
                           uint8_t *data,
                           size_t length)
{
    return BspI2c_ReadRegister(address_7bit, register_address, data, length) ==
           BSP_I2C_OK;
}

static bool App_Mpu6050Write(uint8_t address_7bit,
                            uint8_t register_address,
                            const uint8_t *data,
                            size_t length)
{
    return BspI2c_WriteRegister(address_7bit, register_address, data, length) ==
           BSP_I2C_OK;
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

static void App_CompleteI2cScan(void)
{
    uint8_t identity = 0U;

    App_RecordLogResult(Logger_WriteFormatted(LOG_LEVEL_INFO,
                                              "I2C",
                                              "scan complete devices=%u",
                                              (unsigned int)s_i2c_scanner.found_count));
    if (s_mpu6050_address == 0U)
    {
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
        App_RecordLogResult(
            Logger_Write(LOG_LEVEL_WARN, "MPU6050", "device not found"));
        return;
    }
    if (Mpu6050_Init(&s_mpu6050,
                     s_mpu6050_address,
                     App_Mpu6050Read,
                     App_Mpu6050Write) != MPU6050_OK)
    {
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
        return;
    }
    if ((Mpu6050_ReadWhoAmI(&s_mpu6050, &identity) != MPU6050_OK) ||
        ((identity & 0x7EU) != MPU6050_WHO_AM_I_VALUE))
    {
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
        App_RecordLogResult(Logger_WriteFormatted(LOG_LEVEL_ERROR,
                                                  "MPU6050",
                                                  "WHO_AM_I invalid value=0x%02X",
                                                  (unsigned int)identity));
        return;
    }
    App_RecordLogResult(Logger_WriteFormatted(LOG_LEVEL_INFO,
                                              "MPU6050",
                                              "WHO_AM_I=0x%02X address=0x%02X",
                                              (unsigned int)identity,
                                              (unsigned int)s_mpu6050_address));
    if (Mpu6050_Wake(&s_mpu6050) != MPU6050_OK)
    {
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
        App_RecordLogResult(
            Logger_Write(LOG_LEVEL_ERROR, "MPU6050", "wake failed"));
        return;
    }

    s_sensor_ready = true;
    App_RecordLogResult(Logger_Write(LOG_LEVEL_INFO, "MPU6050", "sensor ready"));
}

static void App_RunI2cScanStep(void)
{
    I2cScanStepResult_t result;

    if (s_i2c_scanner.complete || !I2cScanner_Step(&s_i2c_scanner, &result))
    {
        return;
    }
    if (result.responded)
    {
        App_RecordLogResult(Logger_WriteFormatted(LOG_LEVEL_INFO,
                                                  "I2C",
                                                  "device found address=0x%02X",
                                                  (unsigned int)result.address));
        if ((result.address == MPU6050_ADDRESS_AD0_LOW) ||
            (result.address == MPU6050_ADDRESS_AD0_HIGH))
        {
            s_mpu6050_address = result.address;
        }
    }
    if (result.complete)
    {
        App_CompleteI2cScan();
    }
}

static void App_ReadAndLogSensor(void)
{
    Mpu6050RawData_t raw_data;

    if (Mpu6050_ReadRaw(&s_mpu6050, &raw_data) != MPU6050_OK)
    {
        s_sensor_ready = false;
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
        App_RecordLogResult(
            Logger_Write(LOG_LEVEL_ERROR, "MPU6050", "raw read failed"));
        return;
    }

    App_RecordLogResult(
        Logger_WriteFormatted(LOG_LEVEL_INFO,
                              "MPU6050",
                              "accel=%d,%d,%d gyro=%d,%d,%d",
                              (int)raw_data.accel_x,
                              (int)raw_data.accel_y,
                              (int)raw_data.accel_z,
                              (int)raw_data.gyro_x,
                              (int)raw_data.gyro_y,
                              (int)raw_data.gyro_z));
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
    if (BspI2c_Init() != BSP_I2C_OK)
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
        !SoftwareTimer_Init(&s_health_report_timer, now_ms, APP_HEALTH_REPORT_PERIOD_MS) ||
        !SoftwareTimer_Init(&s_sensor_read_timer, now_ms, APP_SENSOR_READ_PERIOD_MS) ||
        !I2cScanner_Init(&s_i2c_scanner, App_I2cProbe))
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
    s_sensor_ready = false;
    s_mpu6050_address = 0U;
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
    App_RunI2cScanStep();

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

    if (s_sensor_ready && SoftwareTimer_IsDue(&s_sensor_read_timer, now_ms))
    {
        App_ReadAndLogSensor();
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
