#ifndef CONFIG_STORE_H
#define CONFIG_STORE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define CONFIG_SCHEMA_VERSION 1U
#define CONFIG_FLASH_PAGE_SIZE 1024U
#define CONFIG_SLOT_A_ADDRESS 0x0800F800UL
#define CONFIG_SLOT_B_ADDRESS 0x0800FC00UL
#define CONFIG_RECORD_SIZE 54U
#define CONFIG_SAVE_MIN_INTERVAL_MS 5000U

typedef enum { CONFIG_SOURCE_DEFAULTS = 0, CONFIG_SOURCE_SLOT_A, CONFIG_SOURCE_SLOT_B } ConfigSource_t;
typedef enum {
    CONFIG_SAVE_NONE = 0, CONFIG_SAVE_OK, CONFIG_SAVE_INVALID, CONFIG_SAVE_BUSY,
    CONFIG_SAVE_RATE_LIMITED, CONFIG_SAVE_ERASE_FAILED,
    CONFIG_SAVE_PROGRAM_FAILED, CONFIG_SAVE_VERIFY_FAILED
} ConfigSaveStatus_t;

typedef struct {
    uint16_t sensor_period_ms;
    uint16_t telemetry_period_ms;
    uint16_t low_pass_alpha_milli;
    uint16_t gyro_weight_milli;
    uint8_t log_level;
    uint8_t telemetry_enabled;
    uint16_t servo_min_us;
    uint16_t servo_center_us;
    uint16_t servo_max_us;
    uint8_t pid_axis;
    uint8_t pid_direction;
    uint16_t kp_milli;
    uint16_t ki_milli;
    uint16_t kd_milli;
    uint16_t derivative_alpha_milli;
    uint16_t deadband_cdeg;
    int16_t output_min_us;
    int16_t output_max_us;
    uint8_t integral_mode;
} PersistentConfigV1_t;

typedef struct {
    bool (*read)(uint32_t address, uint8_t *data, size_t length);
    bool (*erase_page)(uint32_t address);
    bool (*program)(uint32_t address, const uint8_t *data, size_t length);
    uint32_t (*time_ms)(void);
} ConfigFlashBackend_t;

typedef struct {
    ConfigSource_t loaded_from;
    uint16_t schema_version;
    uint32_t generation;
    uint8_t valid_slot_count;
    ConfigSaveStatus_t last_save_status;
    uint32_t crc_error_count;
    uint32_t invalid_record_count;
    uint32_t unsupported_schema_count;
    uint32_t save_count;
    uint32_t factory_reset_count;
    uint32_t save_rate_limited_count;
    uint32_t last_save_duration_ms;
    bool dirty;
} ConfigStoreStatus_t;

void Config_GetFactoryDefaults(PersistentConfigV1_t *config);
bool ConfigStore_IsConfigValid(const PersistentConfigV1_t *config);
bool ConfigStore_Init(const ConfigFlashBackend_t *backend, uint32_t now_ms,
                      PersistentConfigV1_t *loaded);
bool ConfigStore_Load(PersistentConfigV1_t *loaded);
ConfigSaveStatus_t ConfigStore_Save(const PersistentConfigV1_t *config,
                                    uint32_t now_ms, bool control_safe);
ConfigSaveStatus_t ConfigStore_FactoryReset(uint32_t now_ms, bool control_safe,
                                            PersistentConfigV1_t *defaults);
void ConfigStore_MarkDirty(void);
bool ConfigStore_GetStatus(ConfigStoreStatus_t *status);

#endif
