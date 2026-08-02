#include "calibration_service.h"

#include <stddef.h>

#include "app_config.h"

static CalibrationState_t s_state = CALIBRATION_STATE_IDLE;
static CalibrationResult_t s_result;
static int64_t s_accel_sum_x;
static int64_t s_accel_sum_y;
static int64_t s_accel_sum_z;
static int64_t s_gyro_sum_x;
static int64_t s_gyro_sum_y;
static int64_t s_gyro_sum_z;
static bool s_initialized;

static int64_t CalibrationService_Abs(int32_t value)
{
    return (value < 0) ? -(int64_t)value : (int64_t)value;
}

static bool CalibrationService_IsStationary(const Mpu6500ScaledSample_t *sample)
{
    int64_t magnitude_squared;
    int32_t lower_bound = 1000 - APP_CALIBRATION_ACCEL_TOLERANCE_MG;
    int32_t upper_bound = 1000 + APP_CALIBRATION_ACCEL_TOLERANCE_MG;

    if (sample == NULL)
    {
        return false;
    }
    if ((CalibrationService_Abs(sample->gyro_mdps_x) >
         APP_CALIBRATION_MAX_GYRO_MDPS) ||
        (CalibrationService_Abs(sample->gyro_mdps_y) >
         APP_CALIBRATION_MAX_GYRO_MDPS) ||
        (CalibrationService_Abs(sample->gyro_mdps_z) >
         APP_CALIBRATION_MAX_GYRO_MDPS))
    {
        return false;
    }

    /* 使用平方模长判断1 g，避免校准路径依赖开方和浮点累加。 */
    magnitude_squared =
        ((int64_t)sample->accel_mg_x * sample->accel_mg_x) +
        ((int64_t)sample->accel_mg_y * sample->accel_mg_y) +
        ((int64_t)sample->accel_mg_z * sample->accel_mg_z);
    return (magnitude_squared >= ((int64_t)lower_bound * lower_bound)) &&
           (magnitude_squared <= ((int64_t)upper_bound * upper_bound));
}

static void CalibrationService_Finalize(void)
{
    int32_t average_z;
    int32_t gravity_reference;
    int64_t count = (int64_t)s_result.accepted_samples;

    s_result.gyro_bias_mdps_x = (int32_t)(s_gyro_sum_x / count);
    s_result.gyro_bias_mdps_y = (int32_t)(s_gyro_sum_y / count);
    s_result.gyro_bias_mdps_z = (int32_t)(s_gyro_sum_z / count);
    s_result.accel_bias_mg_x = (int32_t)(s_accel_sum_x / count);
    s_result.accel_bias_mg_y = (int32_t)(s_accel_sum_y / count);
    average_z = (int32_t)(s_accel_sum_z / count);

    /*
     * 静止时Z轴包含重力。偏差应为“测量值减去±1 g”，而不是把Z轴均值
     * 直接校为0，否则姿态计算会丢失重力方向。
     */
    gravity_reference = (average_z >= 0) ? 1000 : -1000;
    s_result.accel_bias_mg_z = average_z - gravity_reference;
    s_result.valid = true;
    s_state = CALIBRATION_STATE_COMPLETE;
}

void CalibrationService_Reset(void)
{
    s_result = (CalibrationResult_t){0};
    s_accel_sum_x = 0;
    s_accel_sum_y = 0;
    s_accel_sum_z = 0;
    s_gyro_sum_x = 0;
    s_gyro_sum_y = 0;
    s_gyro_sum_z = 0;
    s_state = CALIBRATION_STATE_IDLE;
}

bool CalibrationService_Init(void)
{
    CalibrationService_Reset();
    s_initialized = true;
    return true;
}

bool CalibrationService_Start(void)
{
    if (!s_initialized)
    {
        return false;
    }

    CalibrationService_Reset();
    s_state = CALIBRATION_STATE_COLLECTING;
    return true;
}

void CalibrationService_ProcessSample(const Mpu6500ScaledSample_t *sample)
{
    if (!s_initialized || (s_state != CALIBRATION_STATE_COLLECTING))
    {
        return;
    }
    if (!CalibrationService_IsStationary(sample))
    {
        ++s_result.rejected_samples;
        if (s_result.rejected_samples >= APP_CALIBRATION_MAX_REJECTED_SAMPLES)
        {
            s_state = CALIBRATION_STATE_FAILED;
        }
        return;
    }

    s_accel_sum_x += sample->accel_mg_x;
    s_accel_sum_y += sample->accel_mg_y;
    s_accel_sum_z += sample->accel_mg_z;
    s_gyro_sum_x += sample->gyro_mdps_x;
    s_gyro_sum_y += sample->gyro_mdps_y;
    s_gyro_sum_z += sample->gyro_mdps_z;
    ++s_result.accepted_samples;
    if (s_result.accepted_samples >= APP_CALIBRATION_SAMPLE_COUNT)
    {
        CalibrationService_Finalize();
    }
}

CalibrationState_t CalibrationService_GetState(void)
{
    return s_state;
}

bool CalibrationService_GetResult(CalibrationResult_t *result)
{
    if ((result == NULL) || !s_initialized)
    {
        return false;
    }

    *result = s_result;
    return true;
}

const char *CalibrationService_StateToString(CalibrationState_t state)
{
    switch (state)
    {
        case CALIBRATION_STATE_IDLE:
            return "IDLE";
        case CALIBRATION_STATE_COLLECTING:
            return "COLLECTING";
        case CALIBRATION_STATE_COMPLETE:
            return "COMPLETE";
        case CALIBRATION_STATE_FAILED:
            return "FAILED";
        default:
            return "UNKNOWN";
    }
}
