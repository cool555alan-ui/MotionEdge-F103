#include "sensor_service.h"

#include <stddef.h>

#include "app_config.h"

static Mpu6050_t *s_device;
static SoftwareTimer_t s_sample_timer;
static SensorSample_t s_latest_sample;
static bool s_initialized;
static bool s_has_sample;

bool SensorService_Init(Mpu6050_t *device, uint32_t now_ms)
{
    if ((device == NULL) || !device->initialized || !device->awake ||
        !SoftwareTimer_Init(&s_sample_timer, now_ms, APP_SENSOR_SAMPLE_PERIOD_MS))
    {
        return false;
    }

    s_device = device;
    s_latest_sample = (SensorSample_t){0};
    s_initialized = true;
    s_has_sample = false;
    return true;
}

void SensorService_RunOnce(uint32_t now_ms)
{
    Mpu6050RawData_t raw_data;

    if (!s_initialized || !SoftwareTimer_IsDue(&s_sample_timer, now_ms))
    {
        return;
    }

    ++s_latest_sample.sequence;
    s_latest_sample.timestamp_ms = now_ms;
    s_latest_sample.read_success =
        (Mpu6050_ReadRaw(s_device, &raw_data) == MPU6050_OK) &&
        Mpu6050_ScaleRaw(&raw_data, &s_latest_sample.scaled);
    if (!s_latest_sample.read_success)
    {
        s_latest_sample.scaled = (Mpu6050ScaledSample_t){0};
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
