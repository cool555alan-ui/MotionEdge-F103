#include "app_main.h"

#include <inttypes.h>

#include "app_config.h"
#include "app_status.h"
#include "app_version.h"
#include "bsp_i2c.h"
#include "bsp_led.h"
#include "bsp_uart.h"
#include "calibration_service.h"
#include "communication_service.h"
#include "csv_telemetry.h"
#include "health_service.h"
#include "i2c_scanner.h"
#include "logger.h"
#include "motion_service.h"
#include "mpu6500.h"
#include "sensor_service.h"
#include "software_timer.h"

static SoftwareTimer_t s_heartbeat_timer;
static SoftwareTimer_t s_health_report_timer;
static SoftwareTimer_t s_attitude_report_timer;
static SoftwareTimer_t s_calibration_report_timer;
static I2cScanner_t s_i2c_scanner;
static Mpu6500_t s_mpu6500;
static bool s_app_initialized = false;
static bool s_sensor_ready = false;
static uint8_t s_mpu6500_address = 0U;
static uint8_t s_i2c_scan_retry_count = 0U;
static bool s_csv_header_written = false;
static uint32_t s_last_csv_sequence = 0U;
static bool s_has_csv_sequence = false;
static CalibrationState_t s_last_calibration_state = CALIBRATION_STATE_IDLE;
static uint32_t s_next_sensor_recovery_ms = 0U;
static char s_csv_buffer[APP_CSV_BUFFER_SIZE];

static bool App_DefaultUartWriter(const uint8_t *data, size_t length)
{
    return BspUart_Write(data, length) == BSP_UART_OK;
}

static AppUartWriter_t s_uart_writer = App_DefaultUartWriter;

static bool App_UartLogWriter(const uint8_t *data, size_t length)
{
    return (s_uart_writer != NULL) && s_uart_writer(data, length);
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

static bool App_Mpu6500Read(uint8_t address_7bit,
                           uint8_t register_address,
                           uint8_t *data,
                           size_t length)
{
    return BspI2c_ReadRegister(address_7bit, register_address, data, length) ==
           BSP_I2C_OK;
}

static bool App_Mpu6500Write(uint8_t address_7bit,
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

static void App_CompleteI2cScan(uint32_t now_ms)
{
    uint8_t identity = 0U;

    App_RecordLogResult(Logger_WriteFormatted(LOG_LEVEL_INFO,
                                              "I2C",
                                              "scan complete devices=%u",
                                              (unsigned int)s_i2c_scanner.found_count));
    if (s_mpu6500_address == 0U)
    {
        if ((s_i2c_scan_retry_count < APP_I2C_SCAN_MAX_RETRIES) &&
            (BspI2c_RecoverBus() == BSP_I2C_OK) &&
            I2cScanner_Init(&s_i2c_scanner, App_I2cProbe))
        {
            ++s_i2c_scan_retry_count;
            App_RecordLogResult(
                Logger_WriteFormatted(LOG_LEVEL_WARN,
                                      "I2C",
                                      "device not found; recovery retry=%u/%u",
                                      (unsigned int)s_i2c_scan_retry_count,
                                      (unsigned int)APP_I2C_SCAN_MAX_RETRIES));
            return;
        }
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
        App_RecordLogResult(
            Logger_Write(LOG_LEVEL_WARN, "MPU6500", "device not found"));
        return;
    }
    if (Mpu6500_Init(&s_mpu6500,
                     s_mpu6500_address,
                     App_Mpu6500Read,
                     App_Mpu6500Write) != MPU6500_OK)
    {
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
        return;
    }
    if ((Mpu6500_ReadWhoAmI(&s_mpu6500, &identity) != MPU6500_OK) ||
        (s_mpu6500.model == MPU6XXX_MODEL_UNKNOWN))
    {
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
        App_RecordLogResult(Logger_WriteFormatted(LOG_LEVEL_ERROR,
                                                  "MPU6500",
                                                  "WHO_AM_I invalid value=0x%02X",
                                                  (unsigned int)identity));
        return;
    }
    App_RecordLogResult(
        Logger_WriteFormatted(LOG_LEVEL_INFO,
                              "MPU6XXX",
                              "model=%s WHO_AM_I=0x%02X address=0x%02X",
                              Mpu6500_ModelToString(s_mpu6500.model),
                              (unsigned int)identity,
                              (unsigned int)s_mpu6500_address));
    if (Mpu6500_Wake(&s_mpu6500) != MPU6500_OK)
    {
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
        App_RecordLogResult(
            Logger_Write(LOG_LEVEL_ERROR, "MPU6500", "wake failed"));
        return;
    }
    if (!SensorService_Init(&s_mpu6500, now_ms))
    {
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
        App_RecordLogResult(
            Logger_Write(LOG_LEVEL_ERROR, "SENSOR", "service init failed"));
        return;
    }

    s_sensor_ready = true;
    App_RecordLogResult(Logger_Write(LOG_LEVEL_INFO, "MPU6500", "sensor ready"));
}

static void App_RunI2cScanStep(uint32_t now_ms)
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
        if ((result.address == MPU6500_ADDRESS_AD0_LOW) ||
            (result.address == MPU6500_ADDRESS_AD0_HIGH))
        {
            s_mpu6500_address = result.address;
        }
    }
    if (result.complete)
    {
        App_CompleteI2cScan(now_ms);
    }
}

static void App_ReportCalibration(void)
{
    CalibrationResult_t result;
    CalibrationState_t state = CalibrationService_GetState();

    if (!MotionService_GetCalibration(&result))
    {
        return;
    }
    if (state == CALIBRATION_STATE_COLLECTING)
    {
        App_RecordLogResult(
            Logger_WriteFormatted(LOG_LEVEL_INFO,
                                  "CAL",
                                  "state=COLLECTING accepted=%" PRIu32
                                  " rejected=%" PRIu32 " target=%u",
                                  result.accepted_samples,
                                  result.rejected_samples,
                                  (unsigned int)APP_CALIBRATION_SAMPLE_COUNT));
    }
    else if ((state == CALIBRATION_STATE_COMPLETE) &&
             (s_last_calibration_state != CALIBRATION_STATE_COMPLETE))
    {
        App_RecordLogResult(
            Logger_WriteFormatted(LOG_LEVEL_INFO,
                                  "CAL",
                                  "complete gx_bias_mdps=%" PRId32
                                  " gy_bias_mdps=%" PRId32 " gz_bias_mdps=%" PRId32,
                                  result.gyro_bias_mdps_x,
                                  result.gyro_bias_mdps_y,
                                  result.gyro_bias_mdps_z));
    }
    else if ((state == CALIBRATION_STATE_FAILED) &&
             (s_last_calibration_state != CALIBRATION_STATE_FAILED))
    {
        App_RecordLogResult(Logger_Write(LOG_LEVEL_ERROR, "CAL", "calibration failed"));
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
    }
    s_last_calibration_state = state;
}

static void App_WriteTelemetry(const MotionFrame_t *frame)
{
    size_t written;

    if ((frame == NULL) || !frame->valid)
    {
        return;
    }
    if (s_has_csv_sequence && (frame->sequence == s_last_csv_sequence))
    {
        return;
    }
    if (!s_csv_header_written)
    {
        if (!CsvTelemetry_WriteHeader(s_csv_buffer, sizeof(s_csv_buffer), &written) ||
            !App_UartLogWriter((const uint8_t *)s_csv_buffer, written))
        {
            HealthService_RecordLogFailure();
            return;
        }
        s_csv_header_written = true;
    }
    if (!CsvTelemetry_WriteFrame(
            frame, s_csv_buffer, sizeof(s_csv_buffer), &written) ||
        !App_UartLogWriter((const uint8_t *)s_csv_buffer, written))
    {
        HealthService_RecordLogFailure();
        return;
    }
    s_last_csv_sequence = frame->sequence;
    s_has_csv_sequence = true;
}

static void App_RunMotionPipeline(uint32_t now_ms)
{
    MotionServiceState_t motion_state;

    if (!s_sensor_ready)
    {
        return;
    }
    MotionService_RunOnce(now_ms);
    motion_state = MotionService_GetState();
    if (motion_state == MOTION_SERVICE_STATE_DEGRADED)
    {
        (void)AppStatus_SetState(APP_STATE_DEGRADED);
    }
    else if ((motion_state == MOTION_SERVICE_STATE_RUNNING) &&
             (AppStatus_GetState() == APP_STATE_DEGRADED))
    {
        (void)AppStatus_SetState(APP_STATE_RUNNING);
    }
}

static bool App_IsTimeReached(uint32_t now_ms, uint32_t deadline_ms)
{
    return (int32_t)(now_ms - deadline_ms) >= 0;
}

static bool App_ReinitializeSensor(uint32_t now_ms)
{
    uint8_t identity = 0U;
    uint8_t address = s_mpu6500_address;

    if ((BspI2c_RecoverBus() != BSP_I2C_OK) ||
        (BspI2c_IsDeviceReady(address) != BSP_I2C_OK))
    {
        return false;
    }
    if ((Mpu6500_Init(&s_mpu6500, address, App_Mpu6500Read, App_Mpu6500Write) !=
         MPU6500_OK) ||
        (Mpu6500_ReadWhoAmI(&s_mpu6500, &identity) != MPU6500_OK) ||
        (s_mpu6500.model == MPU6XXX_MODEL_UNKNOWN) ||
        (Mpu6500_Wake(&s_mpu6500) != MPU6500_OK) ||
        !SensorService_Init(&s_mpu6500, now_ms) ||
        !MotionService_StartCalibration())
    {
        return false;
    }

    /* 传感器可能已经掉电复位，恢复后必须重新确认身份并重新校准。 */
    s_last_calibration_state = CALIBRATION_STATE_IDLE;
    App_RecordLogResult(
        Logger_WriteFormatted(LOG_LEVEL_INFO,
                              "I2C",
                              "recovery device found address=0x%02X",
                              (unsigned int)address));
    App_RecordLogResult(
        Logger_WriteFormatted(LOG_LEVEL_INFO,
                              "MPU6XXX",
                              "recovery model=%s WHO_AM_I=0x%02X address=0x%02X",
                              Mpu6500_ModelToString(s_mpu6500.model),
                              (unsigned int)identity,
                              (unsigned int)address));
    App_RecordLogResult(
        Logger_Write(LOG_LEVEL_INFO, "CAL", "recovery calibration started"));
    return true;
}

static void App_RunSensorRecovery(uint32_t now_ms)
{
    if ((MotionService_GetState() != MOTION_SERVICE_STATE_DEGRADED) ||
        !App_IsTimeReached(now_ms, s_next_sensor_recovery_ms))
    {
        return;
    }

    s_next_sensor_recovery_ms = now_ms + APP_SENSOR_RECOVERY_PERIOD_MS;
    if (!App_ReinitializeSensor(now_ms))
    {
        App_RecordLogResult(
            Logger_Write(LOG_LEVEL_WARN, "I2C", "runtime sensor recovery pending"));
    }
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
        !SoftwareTimer_Init(
            &s_attitude_report_timer, now_ms, APP_ATTITUDE_REPORT_PERIOD_MS) ||
        !SoftwareTimer_Init(
            &s_calibration_report_timer, now_ms, APP_HEALTH_REPORT_PERIOD_MS) ||
        !I2cScanner_Init(&s_i2c_scanner, App_I2cProbe) ||
        !MotionService_Init(now_ms) || !MotionService_StartCalibration() ||
        !CommunicationService_Init(now_ms))
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
    s_mpu6500_address = 0U;
    s_i2c_scan_retry_count = 0U;
    s_csv_header_written = false;
    s_last_csv_sequence = 0U;
    s_has_csv_sequence = false;
    s_last_calibration_state = CALIBRATION_STATE_IDLE;
    s_next_sensor_recovery_ms = now_ms;
    App_LogStartupInformation();
    return true;
}

void App_SetUartWriter(AppUartWriter_t writer)
{
    s_uart_writer = (writer != NULL) ? writer : App_DefaultUartWriter;
    CommunicationService_SetWriter(s_uart_writer);
}

void App_SensorRunOnce(uint32_t now_ms)
{
    if (!s_app_initialized)
    {
        return;
    }
    HealthService_RecordLoop(now_ms);
    App_RunI2cScanStep(now_ms);
    App_RunMotionPipeline(now_ms);
    App_RunSensorRecovery(now_ms);
}

void App_CommunicationRunOnce(uint32_t now_ms)
{
    (void)now_ms;
    if (s_app_initialized)
    {
        CommunicationService_RunRxOnce();
    }
}

bool App_ProcessCommand(const ProtocolFrame_t *request)
{
    return s_app_initialized && CommunicationService_ProcessCommand(request);
}

void App_TelemetryRunOnce(uint32_t now_ms, const MotionFrame_t *frame)
{
    if (!s_app_initialized)
    {
        return;
    }
    if (CommunicationService_IsProtocolMode())
    {
        CommunicationService_RunTelemetry(now_ms, frame);
        return;
    }
    if (SoftwareTimer_IsDue(&s_calibration_report_timer, now_ms))
    {
        App_ReportCalibration();
    }
    if (SoftwareTimer_IsDue(&s_attitude_report_timer, now_ms))
    {
        App_WriteTelemetry(frame);
    }
}

void App_HealthRunOnce(uint32_t now_ms)
{
    HealthSnapshot_t snapshot;

    if (!s_app_initialized)
    {
        return;
    }
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
    if (!CommunicationService_IsProtocolMode() &&
        SoftwareTimer_IsDue(&s_health_report_timer, now_ms) &&
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

void App_RunOnce(uint32_t now_ms)
{
    MotionFrame_t frame;

    if (!s_app_initialized)
    {
        return;
    }

    App_SensorRunOnce(now_ms);
    App_CommunicationRunOnce(now_ms);
    App_TelemetryRunOnce(
        now_ms, MotionService_GetLatestFrame(&frame) ? &frame : NULL);
    App_HealthRunOnce(now_ms);
}
