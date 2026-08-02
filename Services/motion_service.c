#include "motion_service.h"

#include <math.h>
#include <stddef.h>

#include "app_config.h"
#include "low_pass_filter.h"
#include "sensor_service.h"

#define MOTION_ACCEL_MAX_MG 16000
#define MOTION_GYRO_MAX_MDPS 250000
#define MOTION_ACCEL_MIN_MAGNITUDE_MG 250
#define MOTION_ACCEL_MAX_MAGNITUDE_MG 2000
#define MOTION_ACCEL_SATURATION_MG 15500
#define MOTION_GYRO_SATURATION_MDPS 245000

static LowPassFilter_t s_filters[6];
static AttitudeEstimator_t s_estimator;
static MotionFrame_t s_latest_frame;
static MotionServiceStats_t s_stats;
static MotionServiceState_t s_state;
static Mpu6500ScaledSample_t s_previous_sample;
static uint32_t s_last_sequence;
static uint32_t s_last_timestamp_ms;
static uint32_t s_invalid_count;
static uint32_t s_valid_recovery_count;
static uint32_t s_fixed_count;
static bool s_has_frame;
static bool s_has_previous;
static bool s_initialized;
static bool s_was_calibrated;

static int64_t MotionService_Abs(int32_t value)
{
    return (value < 0) ? -(int64_t)value : (int64_t)value;
}

static bool MotionService_SamplesEqual(const Mpu6500ScaledSample_t *left,
                                       const Mpu6500ScaledSample_t *right)
{
    return (left->accel_mg_x == right->accel_mg_x) &&
           (left->accel_mg_y == right->accel_mg_y) &&
           (left->accel_mg_z == right->accel_mg_z) &&
           (left->gyro_mdps_x == right->gyro_mdps_x) &&
           (left->gyro_mdps_y == right->gyro_mdps_y) &&
           (left->gyro_mdps_z == right->gyro_mdps_z);
}

static uint32_t MotionService_ValidateSample(const SensorSample_t *sample)
{
    uint32_t flags = MOTION_SAMPLE_FLAG_NONE;
    const Mpu6500ScaledSample_t *scaled = &sample->scaled;
    int64_t magnitude_squared;

    if (!sample->read_success)
    {
        return MOTION_SAMPLE_FLAG_BUS_ERROR;
    }
    if (s_has_previous && (sample->timestamp_ms == s_last_timestamp_ms))
    {
        flags |= MOTION_SAMPLE_FLAG_STALE;
    }
    if ((scaled->accel_mg_x == 0) && (scaled->accel_mg_y == 0) &&
        (scaled->accel_mg_z == 0) && (scaled->gyro_mdps_x == 0) &&
        (scaled->gyro_mdps_y == 0) && (scaled->gyro_mdps_z == 0))
    {
        flags |= MOTION_SAMPLE_FLAG_ALL_ZERO;
    }
    if ((MotionService_Abs(scaled->accel_mg_x) > MOTION_ACCEL_MAX_MG) ||
        (MotionService_Abs(scaled->accel_mg_y) > MOTION_ACCEL_MAX_MG) ||
        (MotionService_Abs(scaled->accel_mg_z) > MOTION_ACCEL_MAX_MG))
    {
        flags |= MOTION_SAMPLE_FLAG_ACCEL_RANGE;
    }
    if ((MotionService_Abs(scaled->gyro_mdps_x) > MOTION_GYRO_MAX_MDPS) ||
        (MotionService_Abs(scaled->gyro_mdps_y) > MOTION_GYRO_MAX_MDPS) ||
        (MotionService_Abs(scaled->gyro_mdps_z) > MOTION_GYRO_MAX_MDPS))
    {
        flags |= MOTION_SAMPLE_FLAG_GYRO_RANGE;
    }

    magnitude_squared =
        ((int64_t)scaled->accel_mg_x * scaled->accel_mg_x) +
        ((int64_t)scaled->accel_mg_y * scaled->accel_mg_y) +
        ((int64_t)scaled->accel_mg_z * scaled->accel_mg_z);
    if ((magnitude_squared <
         ((int64_t)MOTION_ACCEL_MIN_MAGNITUDE_MG *
          MOTION_ACCEL_MIN_MAGNITUDE_MG)) ||
        (magnitude_squared >
         ((int64_t)MOTION_ACCEL_MAX_MAGNITUDE_MG *
          MOTION_ACCEL_MAX_MAGNITUDE_MG)))
    {
        flags |= MOTION_SAMPLE_FLAG_ACCEL_RANGE;
    }
    if ((MotionService_Abs(scaled->accel_mg_x) >= MOTION_ACCEL_SATURATION_MG) ||
        (MotionService_Abs(scaled->accel_mg_y) >= MOTION_ACCEL_SATURATION_MG) ||
        (MotionService_Abs(scaled->accel_mg_z) >= MOTION_ACCEL_SATURATION_MG) ||
        (MotionService_Abs(scaled->gyro_mdps_x) >= MOTION_GYRO_SATURATION_MDPS) ||
        (MotionService_Abs(scaled->gyro_mdps_y) >= MOTION_GYRO_SATURATION_MDPS) ||
        (MotionService_Abs(scaled->gyro_mdps_z) >= MOTION_GYRO_SATURATION_MDPS))
    {
        flags |= MOTION_SAMPLE_FLAG_SATURATED;
    }

    if (s_has_previous && MotionService_SamplesEqual(scaled, &s_previous_sample))
    {
        ++s_fixed_count;
        if (s_fixed_count >= APP_SENSOR_FIXED_SAMPLE_LIMIT)
        {
            flags |= MOTION_SAMPLE_FLAG_FIXED;
        }
    }
    else
    {
        s_fixed_count = 0U;
    }
    return flags;
}

static void MotionService_ApplyCalibration(const Mpu6500ScaledSample_t *input,
                                           const CalibrationResult_t *calibration,
                                           Mpu6500ScaledSample_t *output)
{
    *output = *input;
    if (!calibration->valid)
    {
        return;
    }

    output->accel_mg_x -= calibration->accel_bias_mg_x;
    output->accel_mg_y -= calibration->accel_bias_mg_y;
    output->accel_mg_z -= calibration->accel_bias_mg_z;
    output->gyro_mdps_x -= calibration->gyro_bias_mdps_x;
    output->gyro_mdps_y -= calibration->gyro_bias_mdps_y;
    output->gyro_mdps_z -= calibration->gyro_bias_mdps_z;
}

static bool MotionService_FilterSample(const Mpu6500ScaledSample_t *input,
                                       Mpu6500ScaledSample_t *output,
                                       bool reset)
{
    const int32_t values[6] = {input->accel_mg_x,
                               input->accel_mg_y,
                               input->accel_mg_z,
                               input->gyro_mdps_x,
                               input->gyro_mdps_y,
                               input->gyro_mdps_z};
    int32_t *destinations[6] = {&output->accel_mg_x,
                                &output->accel_mg_y,
                                &output->accel_mg_z,
                                &output->gyro_mdps_x,
                                &output->gyro_mdps_y,
                                &output->gyro_mdps_z};
    uint32_t index;

    for (index = 0U; index < 6U; ++index)
    {
        float filtered;
        if (reset && !LowPassFilter_Reset(&s_filters[index], (float)values[index]))
        {
            return false;
        }
        if (!LowPassFilter_Update(&s_filters[index], (float)values[index], &filtered))
        {
            return false;
        }
        *destinations[index] = (int32_t)lroundf(filtered);
    }
    return true;
}

static void MotionService_RecordInvalid(void)
{
    ++s_stats.invalid_samples;
    ++s_stats.dropped_samples;
    ++s_invalid_count;
    s_valid_recovery_count = 0U;
    if (s_invalid_count >= APP_SENSOR_MAX_CONSECUTIVE_INVALID)
    {
        s_state = MOTION_SERVICE_STATE_DEGRADED;
    }
}

bool MotionService_Init(uint32_t now_ms)
{
    uint32_t index;
    float alpha = (float)APP_LOW_PASS_ALPHA_MILLI / 1000.0F;

    (void)now_ms;
    for (index = 0U; index < 6U; ++index)
    {
        if (!LowPassFilter_Init(&s_filters[index], alpha))
        {
            return false;
        }
    }
    if (!AttitudeEstimator_Init(&s_estimator) || !CalibrationService_Init())
    {
        return false;
    }

    s_latest_frame = (MotionFrame_t){0};
    s_stats = (MotionServiceStats_t){0};
    s_previous_sample = (Mpu6500ScaledSample_t){0};
    s_last_sequence = 0U;
    s_last_timestamp_ms = 0U;
    s_invalid_count = 0U;
    s_valid_recovery_count = 0U;
    s_fixed_count = 0U;
    s_has_frame = false;
    s_has_previous = false;
    s_was_calibrated = false;
    s_state = MOTION_SERVICE_STATE_IDLE;
    s_initialized = true;
    return true;
}

bool MotionService_StartCalibration(void)
{
    if (!s_initialized || !CalibrationService_Start())
    {
        return false;
    }
    s_state = MOTION_SERVICE_STATE_CALIBRATING;
    s_was_calibrated = false;
    return true;
}

void MotionService_RunOnce(uint32_t now_ms)
{
    SensorSample_t sensor_sample;
    CalibrationResult_t calibration;
    uint32_t flags;
    bool newly_calibrated;

    SensorService_RunOnce(now_ms);
    if (!s_initialized || !SensorService_GetLatestSample(&sensor_sample) ||
        (sensor_sample.sequence == s_last_sequence))
    {
        return;
    }
    s_last_sequence = sensor_sample.sequence;
    flags = MotionService_ValidateSample(&sensor_sample);
    s_previous_sample = sensor_sample.scaled;
    s_last_timestamp_ms = sensor_sample.timestamp_ms;
    s_has_previous = sensor_sample.read_success;
    if (flags != MOTION_SAMPLE_FLAG_NONE)
    {
        MotionService_RecordInvalid();
        return;
    }

    s_invalid_count = 0U;
    if (s_state == MOTION_SERVICE_STATE_DEGRADED)
    {
        ++s_valid_recovery_count;
        if (s_valid_recovery_count >= APP_SENSOR_MAX_CONSECUTIVE_INVALID)
        {
            ++s_stats.recovery_count;
            s_state = (CalibrationService_GetState() == CALIBRATION_STATE_COLLECTING)
                          ? MOTION_SERVICE_STATE_CALIBRATING
                          : MOTION_SERVICE_STATE_RUNNING;
        }
    }

    if (CalibrationService_GetState() == CALIBRATION_STATE_COLLECTING)
    {
        CalibrationService_ProcessSample(&sensor_sample.scaled);
    }
    if (!CalibrationService_GetResult(&calibration))
    {
        MotionService_RecordInvalid();
        return;
    }
    if (CalibrationService_GetState() == CALIBRATION_STATE_FAILED)
    {
        s_state = MOTION_SERVICE_STATE_DEGRADED;
    }
    newly_calibrated = calibration.valid && !s_was_calibrated;

    s_latest_frame.timestamp_ms = sensor_sample.timestamp_ms;
    s_latest_frame.sequence = sensor_sample.sequence;
    s_latest_frame.status_flags = flags;
    s_latest_frame.raw_scaled = sensor_sample.scaled;
    MotionService_ApplyCalibration(
        &sensor_sample.scaled, &calibration, &s_latest_frame.calibrated_sample);
    if (!MotionService_FilterSample(
            &s_latest_frame.calibrated_sample, &s_latest_frame.filtered, newly_calibrated))
    {
        MotionService_RecordInvalid();
        return;
    }
    if (newly_calibrated)
    {
        if (!AttitudeEstimator_Reset(
                &s_estimator, &s_latest_frame.filtered, sensor_sample.timestamp_ms))
        {
            MotionService_RecordInvalid();
            return;
        }
        s_latest_frame.attitude.roll_cdeg =
            (int32_t)lroundf(s_estimator.roll_deg * 100.0F);
        s_latest_frame.attitude.pitch_cdeg =
            (int32_t)lroundf(s_estimator.pitch_deg * 100.0F);
        s_latest_frame.attitude.accel_roll_cdeg =
            (int32_t)lroundf(s_estimator.accel_roll_deg * 100.0F);
        s_latest_frame.attitude.accel_pitch_cdeg =
            (int32_t)lroundf(s_estimator.accel_pitch_deg * 100.0F);
        s_latest_frame.attitude.valid = true;
    }
    else if (!AttitudeEstimator_Update(&s_estimator,
                                       &s_latest_frame.filtered,
                                       sensor_sample.timestamp_ms,
                                       &s_latest_frame.attitude))
    {
        ++s_stats.dropped_samples;
        return;
    }

    s_latest_frame.calibrated = calibration.valid;
    s_latest_frame.valid = true;
    s_was_calibrated = calibration.valid;
    s_has_frame = true;
    ++s_stats.successful_samples;
    if ((s_state != MOTION_SERVICE_STATE_DEGRADED) &&
        (CalibrationService_GetState() == CALIBRATION_STATE_COMPLETE))
    {
        s_state = MOTION_SERVICE_STATE_RUNNING;
    }
}

bool MotionService_GetLatestFrame(MotionFrame_t *frame)
{
    if ((frame == NULL) || !s_initialized || !s_has_frame)
    {
        return false;
    }
    *frame = s_latest_frame;
    return true;
}

bool MotionService_GetCalibration(CalibrationResult_t *result)
{
    return s_initialized && CalibrationService_GetResult(result);
}

MotionServiceState_t MotionService_GetState(void)
{
    return s_state;
}

const char *MotionService_StateToString(MotionServiceState_t state)
{
    switch (state)
    {
        case MOTION_SERVICE_STATE_IDLE:
            return "IDLE";
        case MOTION_SERVICE_STATE_CALIBRATING:
            return "CALIBRATING";
        case MOTION_SERVICE_STATE_RUNNING:
            return "RUNNING";
        case MOTION_SERVICE_STATE_DEGRADED:
            return "DEGRADED";
        default:
            return "UNKNOWN";
    }
}

bool MotionService_GetStats(MotionServiceStats_t *stats)
{
    if ((stats == NULL) || !s_initialized)
    {
        return false;
    }
    *stats = s_stats;
    return true;
}

bool MotionService_SetFilterConfig(uint16_t alpha_milli,
                                   uint16_t gyro_weight_milli)
{
    uint32_t index;
    float alpha = (float)alpha_milli / 1000.0F;
    float gyro_weight = (float)gyro_weight_milli / 1000.0F;

    if ((alpha_milli < 1U) || (alpha_milli > 1000U) ||
        (gyro_weight_milli < 500U) || (gyro_weight_milli > 999U))
    {
        return false;
    }
    if (s_initialized)
    {
        for (index = 0U; index < 6U; ++index)
        {
            s_filters[index].alpha = alpha;
        }
        return AttitudeEstimator_SetGyroWeight(&s_estimator, gyro_weight);
    }
    return true;
}
