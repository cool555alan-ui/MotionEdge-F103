#include "attitude_estimator.h"

#include <math.h>
#include <stddef.h>

#include "app_config.h"

#define ATTITUDE_RAD_TO_DEG 57.29577951308232F
#define ATTITUDE_MAX_DT_MS 200U

static bool AttitudeEstimator_CalculateAccelAngles(const Mpu6500ScaledSample_t *sample,
                                                   float *roll_deg,
                                                   float *pitch_deg)
{
    float ax;
    float ay;
    float az;
    float pitch_denominator;

    if ((sample == NULL) || (roll_deg == NULL) || (pitch_deg == NULL))
    {
        return false;
    }

    /*
     * 坐标系定义为X轴向前、Y轴向右、Z轴向上。Roll绕X轴、Pitch绕Y轴，
     * atan2f保留象限；Pitch分母使用Y/Z平方和，避免单轴接近0时发散。
     */
    ax = (float)sample->accel_mg_x;
    ay = (float)sample->accel_mg_y;
    az = (float)sample->accel_mg_z;
    pitch_denominator = sqrtf((ay * ay) + (az * az));
    *roll_deg = atan2f(ay, az) * ATTITUDE_RAD_TO_DEG;
    *pitch_deg = atan2f(-ax, pitch_denominator) * ATTITUDE_RAD_TO_DEG;
    return isfinite(*roll_deg) && isfinite(*pitch_deg);
}

static bool AttitudeEstimator_WriteOutput(const AttitudeEstimator_t *estimator,
                                          AttitudeOutput_t *output)
{
    if ((estimator == NULL) || (output == NULL) || !isfinite(estimator->roll_deg) ||
        !isfinite(estimator->pitch_deg) || !isfinite(estimator->accel_roll_deg) ||
        !isfinite(estimator->accel_pitch_deg))
    {
        return false;
    }

    output->roll_cdeg = (int32_t)lroundf(estimator->roll_deg * 100.0F);
    output->pitch_cdeg = (int32_t)lroundf(estimator->pitch_deg * 100.0F);
    output->accel_roll_cdeg = (int32_t)lroundf(estimator->accel_roll_deg * 100.0F);
    output->accel_pitch_cdeg =
        (int32_t)lroundf(estimator->accel_pitch_deg * 100.0F);
    output->valid = true;
    return true;
}

bool AttitudeEstimator_Init(AttitudeEstimator_t *estimator)
{
    if (estimator == NULL)
    {
        return false;
    }

    estimator->roll_deg = 0.0F;
    estimator->pitch_deg = 0.0F;
    estimator->accel_roll_deg = 0.0F;
    estimator->accel_pitch_deg = 0.0F;
    estimator->gyro_roll_deg = 0.0F;
    estimator->gyro_pitch_deg = 0.0F;
    estimator->last_timestamp_ms = 0U;
    estimator->gyro_weight =
        (float)APP_COMPLEMENTARY_GYRO_WEIGHT_MILLI / 1000.0F;
    estimator->initialized = false;
    return true;
}

bool AttitudeEstimator_Reset(AttitudeEstimator_t *estimator,
                             const Mpu6500ScaledSample_t *sample,
                             uint32_t timestamp_ms)
{
    float roll_deg;
    float pitch_deg;

    if ((estimator == NULL) ||
        !AttitudeEstimator_CalculateAccelAngles(sample, &roll_deg, &pitch_deg))
    {
        return false;
    }

    estimator->roll_deg = roll_deg;
    estimator->pitch_deg = pitch_deg;
    estimator->accel_roll_deg = roll_deg;
    estimator->accel_pitch_deg = pitch_deg;
    estimator->gyro_roll_deg = roll_deg;
    estimator->gyro_pitch_deg = pitch_deg;
    estimator->last_timestamp_ms = timestamp_ms;
    estimator->initialized = true;
    return true;
}

bool AttitudeEstimator_Update(AttitudeEstimator_t *estimator,
                              const Mpu6500ScaledSample_t *sample,
                              uint32_t timestamp_ms,
                              AttitudeOutput_t *output)
{
    uint32_t elapsed_ms;
    float dt_seconds;
    float gyro_weight;
    float accel_weight;
    float predicted_roll;
    float predicted_pitch;

    if ((estimator == NULL) || (sample == NULL) || (output == NULL))
    {
        return false;
    }
    output->valid = false;
    if (!estimator->initialized)
    {
        if (!AttitudeEstimator_Reset(estimator, sample, timestamp_ms))
        {
            return false;
        }
        return AttitudeEstimator_WriteOutput(estimator, output);
    }

    /*
     * 无符号减法使毫秒计数器回绕时仍得到正确间隔。0或超过200 ms的间隔
     * 不参与积分，避免重复时间戳和长时间停顿造成角度跳变。
     */
    elapsed_ms = timestamp_ms - estimator->last_timestamp_ms;
    if (elapsed_ms == 0U)
    {
        return false;
    }
    if (elapsed_ms > ATTITUDE_MAX_DT_MS)
    {
        (void)AttitudeEstimator_Reset(estimator, sample, timestamp_ms);
        return false;
    }
    if (!AttitudeEstimator_CalculateAccelAngles(
            sample, &estimator->accel_roll_deg, &estimator->accel_pitch_deg))
    {
        return false;
    }

    dt_seconds = (float)elapsed_ms / 1000.0F;
    predicted_roll =
        estimator->roll_deg + (((float)sample->gyro_mdps_x / 1000.0F) * dt_seconds);
    predicted_pitch =
        estimator->pitch_deg + (((float)sample->gyro_mdps_y / 1000.0F) * dt_seconds);
    gyro_weight = estimator->gyro_weight;
    accel_weight = 1.0F - gyro_weight;

    estimator->gyro_roll_deg = predicted_roll;
    estimator->gyro_pitch_deg = predicted_pitch;
    estimator->roll_deg =
        (gyro_weight * predicted_roll) + (accel_weight * estimator->accel_roll_deg);
    estimator->pitch_deg =
        (gyro_weight * predicted_pitch) + (accel_weight * estimator->accel_pitch_deg);
    estimator->last_timestamp_ms = timestamp_ms;
    return AttitudeEstimator_WriteOutput(estimator, output);
}

bool AttitudeEstimator_SetGyroWeight(AttitudeEstimator_t *estimator,
                                    float gyro_weight)
{
    if ((estimator == NULL) || !isfinite(gyro_weight) ||
        (gyro_weight < 0.5F) || (gyro_weight > 0.999F))
    {
        return false;
    }
    estimator->gyro_weight = gyro_weight;
    return true;
}
