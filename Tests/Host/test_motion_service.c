#include <string.h>

#include "app_config.h"
#include "motion_service.h"
#include "sensor_service.h"
#include "test_support.h"

static uint8_t s_motion_frame[14];
static bool s_motion_read_success = true;

static void SetWord(size_t offset, int16_t value)
{
    uint16_t encoded = (uint16_t)value;
    s_motion_frame[offset] = (uint8_t)(encoded >> 8U);
    s_motion_frame[offset + 1U] = (uint8_t)encoded;
}

static void SetMotionRaw(int16_t ax,
                         int16_t ay,
                         int16_t az,
                         int16_t gx,
                         int16_t gy,
                         int16_t gz)
{
    (void)memset(s_motion_frame, 0, sizeof(s_motion_frame));
    SetWord(0U, ax);
    SetWord(2U, ay);
    SetWord(4U, az);
    SetWord(8U, gx);
    SetWord(10U, gy);
    SetWord(12U, gz);
}

static bool MotionRead(uint8_t address,
                       uint8_t reg,
                       uint8_t *data,
                       size_t length)
{
    (void)address;
    if (!s_motion_read_success || (data == NULL))
    {
        return false;
    }
    if ((reg == 0x75U) && (length == 1U))
    {
        data[0] = MPU6500_WHO_AM_I_VALUE;
        return true;
    }
    if ((reg == 0x3BU) && (length == sizeof(s_motion_frame)))
    {
        (void)memcpy(data, s_motion_frame, sizeof(s_motion_frame));
        return true;
    }
    return false;
}

static bool MotionWrite(uint8_t address,
                        uint8_t reg,
                        const uint8_t *data,
                        size_t length)
{
    (void)address;
    (void)reg;
    return (data != NULL) && (length == 1U);
}

void TestMotionService_Run(TestContext_t *context)
{
    Mpu6500_t device = {0};
    MotionFrame_t frame;
    MotionServiceStats_t stats;
    CalibrationResult_t calibration;
    uint32_t now_ms = 0U;
    uint32_t index;
    uint32_t successful_before;

    TEST_EXPECT(context,
                Mpu6500_Init(&device,
                             MPU6500_ADDRESS_AD0_LOW,
                             MotionRead,
                             MotionWrite) == MPU6500_OK);
    TEST_EXPECT(context, Mpu6500_Wake(&device) == MPU6500_OK);
    TEST_EXPECT(context, SensorService_Init(&device, now_ms));
    TEST_EXPECT(context, MotionService_Init(now_ms));
    TEST_EXPECT(context, MotionService_StartCalibration());
    for (index = 0U; index < APP_CALIBRATION_SAMPLE_COUNT; ++index)
    {
        SetMotionRaw((index & 1U) ? 32 : -32, 0, 16384, 13, -7, 5);
        now_ms += APP_SENSOR_SAMPLE_PERIOD_MS;
        MotionService_RunOnce(now_ms);
    }
    TEST_EXPECT(context, MotionService_GetCalibration(&calibration));
    TEST_EXPECT(context, calibration.valid);
    TEST_EXPECT(context, MotionService_GetLatestFrame(&frame));
    TEST_EXPECT(context, frame.calibrated);
    TEST_EXPECT(context, frame.valid);
    TEST_EXPECT(context, MotionService_GetState() == MOTION_SERVICE_STATE_RUNNING);
    TEST_EXPECT(context, MotionService_GetStats(&stats));
    successful_before = stats.successful_samples;
    MotionService_RunOnce(now_ms);
    TEST_EXPECT(context, MotionService_GetStats(&stats));
    TEST_EXPECT(context, stats.successful_samples == successful_before);
    s_motion_read_success = false;
    for (index = 0U; index < APP_SENSOR_MAX_CONSECUTIVE_INVALID; ++index)
    {
        now_ms += APP_SENSOR_SAMPLE_PERIOD_MS;
        MotionService_RunOnce(now_ms);
    }
    TEST_EXPECT(context, MotionService_GetState() == MOTION_SERVICE_STATE_DEGRADED);
    s_motion_read_success = true;
    for (index = 0U; index < APP_SENSOR_MAX_CONSECUTIVE_INVALID; ++index)
    {
        SetMotionRaw((index & 1U) ? 48 : -48, 0, 16384, 13, -7, 5);
        now_ms += APP_SENSOR_SAMPLE_PERIOD_MS;
        MotionService_RunOnce(now_ms);
    }
    TEST_EXPECT(context, MotionService_GetState() == MOTION_SERVICE_STATE_RUNNING);
    TEST_EXPECT(context, MotionService_GetStats(&stats));
    TEST_EXPECT(context, stats.invalid_samples >= APP_SENSOR_MAX_CONSECUTIVE_INVALID);
    TEST_EXPECT(context, stats.recovery_count == 1U);
    SetMotionRaw(0, 0, 0, 0, 0, 0);
    for (index = 0U; index < APP_SENSOR_MAX_CONSECUTIVE_INVALID; ++index)
    {
        now_ms += APP_SENSOR_SAMPLE_PERIOD_MS;
        MotionService_RunOnce(now_ms);
    }
    TEST_EXPECT(context, MotionService_GetState() == MOTION_SERVICE_STATE_DEGRADED);
    for (index = 0U; index < APP_SENSOR_MAX_CONSECUTIVE_INVALID; ++index)
    {
        SetMotionRaw((index & 1U) ? 64 : -64, 0, 16384, 13, -7, 5);
        now_ms += APP_SENSOR_SAMPLE_PERIOD_MS;
        MotionService_RunOnce(now_ms);
    }
    TEST_EXPECT(context, MotionService_GetState() == MOTION_SERVICE_STATE_RUNNING);
    TEST_EXPECT(context, MotionService_GetStats(&stats));
    TEST_EXPECT(context, stats.recovery_count == 2U);
    TEST_EXPECT(context,
                strcmp(MotionService_StateToString((MotionServiceState_t)99),
                       "UNKNOWN") == 0);
    TEST_EXPECT(context, !MotionService_GetLatestFrame(NULL));
}
