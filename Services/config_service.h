#ifndef CONFIG_SERVICE_H
#define CONFIG_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

#define CONFIG_SENSOR_PERIOD_MIN_MS 5U
#define CONFIG_SENSOR_PERIOD_MAX_MS 100U
#define CONFIG_TELEMETRY_PERIOD_MIN_MS 20U
#define CONFIG_TELEMETRY_PERIOD_MAX_MS 5000U
#define CONFIG_ALPHA_MIN_MILLI 1U
#define CONFIG_ALPHA_MAX_MILLI 1000U
#define CONFIG_GYRO_WEIGHT_MIN_MILLI 500U
#define CONFIG_GYRO_WEIGHT_MAX_MILLI 999U

typedef struct
{
    uint16_t sensor_sample_period_ms;
    uint16_t telemetry_period_ms;
    uint16_t low_pass_alpha_milli;
    uint16_t complementary_gyro_weight_milli;
    uint8_t log_level;
    bool telemetry_enabled;
} RuntimeConfig_t;

/** 使用编译期默认值初始化RAM配置。 */
bool ConfigService_Init(void);
bool ConfigService_Get(RuntimeConfig_t *config);
/** 完整校验后原子更新配置；任一字段非法时不生效。 */
bool ConfigService_Set(const RuntimeConfig_t *config);

#endif /* CONFIG_SERVICE_H */
