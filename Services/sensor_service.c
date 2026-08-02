#include "sensor_service.h"

#include <stddef.h>

#include "app_config.h"

static Mpu6500_t *s_device;
static SoftwareTimer_t s_sample_timer;
static SensorSample_t s_latest_sample;
static bool s_initialized;
static bool s_has_sample;
static uint16_t s_period_ms = APP_SENSOR_SAMPLE_PERIOD_MS;

bool SensorService_Init(Mpu6500_t *device, uint32_t now_ms)
{
    if ((device == NULL) || !device->initialized || !device->awake ||
        !SoftwareTimer_Init(&s_sample_timer, now_ms, s_period_ms))
    {
        return false;
    }

    s_device = device;
    s_latest_sample = (SensorSample_t){0};
    s_initialized = true;
    s_has_sample = false;
    return true;
}

bool SensorService_SetSamplePeriod(uint16_t period_ms)
{
    if (period_ms == 0U)
    {
        return false;
    }
    s_period_ms = period_ms;
    if (s_initialized)
    {
        s_sample_timer.period_ms = period_ms;
    }
    return true;
}

void SensorService_RunOnce(uint32_t now_ms)
{
    Mpu6500RawData_t raw_data;

    if (!s_initialized || !SoftwareTimer_IsDue(&s_sample_timer, now_ms))
    {
        return;
    }

    ++s_latest_sample.sequence;
    s_latest_sample.timestamp_ms = now_ms;
    s_latest_sample.read_success =
        (Mpu6500_ReadRaw(s_device, &raw_data) == MPU6500_OK) &&
        Mpu6500_ScaleRaw(&raw_data, &s_latest_sample.scaled);
    if (!s_latest_sample.read_success)
    {
        s_latest_sample.scaled = (Mpu6500ScaledSample_t){0};
    }
    s_has_sample = true;
}

bool SensorService_GetLatestSample(SensorSample_t *sample)
{
    if ((sample == NULL) || !s_initialized || !s_has_sample)
    {
        return false;
    }

    *sample = s_latest_sample;
    return true;
}
