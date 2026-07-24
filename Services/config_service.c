#include "config_service.h"

#include <stddef.h>

#include "app_config.h"
#include "logger.h"
#include "motion_service.h"
#include "sensor_service.h"

static RuntimeConfig_t s_config;
static bool s_initialized;

static bool IsValid(const RuntimeConfig_t *config)
{
    return (config != NULL) &&
           (config->sensor_sample_period_ms >= CONFIG_SENSOR_PERIOD_MIN_MS) &&
           (config->sensor_sample_period_ms <= CONFIG_SENSOR_PERIOD_MAX_MS) &&
           (config->telemetry_period_ms >= CONFIG_TELEMETRY_PERIOD_MIN_MS) &&
           (config->telemetry_period_ms <= CONFIG_TELEMETRY_PERIOD_MAX_MS) &&
           (config->low_pass_alpha_milli >= CONFIG_ALPHA_MIN_MILLI) &&
           (config->low_pass_alpha_milli <= CONFIG_ALPHA_MAX_MILLI) &&
           (config->complementary_gyro_weight_milli >=
            CONFIG_GYRO_WEIGHT_MIN_MILLI) &&
           (config->complementary_gyro_weight_milli <=
            CONFIG_GYRO_WEIGHT_MAX_MILLI) &&
           (config->log_level <= (uint8_t)LOG_LEVEL_NONE);
}

bool ConfigService_Init(void)
{
    s_config.sensor_sample_period_ms = APP_SENSOR_SAMPLE_PERIOD_MS;
    s_config.telemetry_period_ms = APP_ATTITUDE_REPORT_PERIOD_MS;
    s_config.low_pass_alpha_milli = APP_LOW_PASS_ALPHA_MILLI;
    s_config.complementary_gyro_weight_milli =
        APP_COMPLEMENTARY_GYRO_WEIGHT_MILLI;
    s_config.log_level = APP_DEFAULT_LOG_LEVEL;
    s_config.telemetry_enabled = APP_DEFAULT_TELEMETRY_ENABLED != 0U;
    s_initialized = true;
    return true;
}

bool ConfigService_Get(RuntimeConfig_t *config)
{
    if ((config == NULL) || !s_initialized)
    {
        return false;
    }
    *config = s_config;
    return true;
}

bool ConfigService_Set(const RuntimeConfig_t *config)
{
    if (!s_initialized || !IsValid(config))
    {
        return false;
    }
    /* 所有字段先校验，再通知服务，确保不会出现部分配置生效。 */
    if (!SensorService_SetSamplePeriod(config->sensor_sample_period_ms) ||
        !MotionService_SetFilterConfig(config->low_pass_alpha_milli,
                                       config->complementary_gyro_weight_milli) ||
        !Logger_SetLevel((LogLevel_t)config->log_level))
    {
        return false;
    }
    s_config = *config;
    return true;
}
