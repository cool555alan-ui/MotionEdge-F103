#include <string.h>

#include "app_config.h"
#include "calibration_service.h"
#include "test_support.h"

void TestCalibrationService_Run(TestContext_t *context)
{
    CalibrationResult_t result;
    Mpu6500ScaledSample_t stationary = {20, -10, 1030, 100, -50, 75};
    Mpu6500ScaledSample_t moving = {500, 500, 500, 6000, 0, 0};
    Mpu6500ScaledSample_t inverted = {10, 5, -1020, 20, 30, 40};
    uint32_t index;

    TEST_EXPECT(context, CalibrationService_Init());
    TEST_EXPECT(context, CalibrationService_GetState() == CALIBRATION_STATE_IDLE);
    TEST_EXPECT(context, !CalibrationService_GetResult(NULL));
    TEST_EXPECT(context, CalibrationService_Start());
    CalibrationService_ProcessSample(&moving);
    TEST_EXPECT(context, CalibrationService_GetResult(&result));
    TEST_EXPECT(context, result.accepted_samples == 0U);
    TEST_EXPECT(context, result.rejected_samples == 1U);
    for (index = 0U; index < APP_CALIBRATION_SAMPLE_COUNT; ++index)
    {
        CalibrationService_ProcessSample(&stationary);
    }
    TEST_EXPECT(context,
                CalibrationService_GetState() == CALIBRATION_STATE_COMPLETE);
    TEST_EXPECT(context, CalibrationService_GetResult(&result));
    TEST_EXPECT(context, result.valid);
    TEST_EXPECT(context, result.accepted_samples == APP_CALIBRATION_SAMPLE_COUNT);
    TEST_EXPECT(context, result.gyro_bias_mdps_x == 100);
    TEST_EXPECT(context, result.gyro_bias_mdps_y == -50);
    TEST_EXPECT(context, result.gyro_bias_mdps_z == 75);
    TEST_EXPECT(context, result.accel_bias_mg_x == 20);
    TEST_EXPECT(context, result.accel_bias_mg_y == -10);
    TEST_EXPECT(context, result.accel_bias_mg_z == 30);
    TEST_EXPECT(context, CalibrationService_Start());
    for (index = 0U; index < APP_CALIBRATION_SAMPLE_COUNT; ++index)
    {
        CalibrationService_ProcessSample(&inverted);
    }
    TEST_EXPECT(context, CalibrationService_GetResult(&result));
    TEST_EXPECT(context, result.valid);
    TEST_EXPECT(context, result.accel_bias_mg_z == -20);
    TEST_EXPECT(context, CalibrationService_Start());
    for (index = 0U; index < APP_CALIBRATION_MAX_REJECTED_SAMPLES; ++index)
    {
        CalibrationService_ProcessSample(&moving);
    }
    TEST_EXPECT(context, CalibrationService_GetState() == CALIBRATION_STATE_FAILED);
    TEST_EXPECT(context, CalibrationService_GetResult(&result));
    TEST_EXPECT(context,
                result.rejected_samples == APP_CALIBRATION_MAX_REJECTED_SAMPLES);
    TEST_EXPECT(context, !result.valid);
    CalibrationService_Reset();
    TEST_EXPECT(context, CalibrationService_GetState() == CALIBRATION_STATE_IDLE);
    TEST_EXPECT(context,
                strcmp(CalibrationService_StateToString((CalibrationState_t)99),
                       "UNKNOWN") == 0);
}
