#include "config_store.h"

#include <stddef.h>

#include "crc16.h"

#define CONFIG_MAGIC 0x4746434DU /* "MCFG" little-endian */
#define CONFIG_HEADER_SIZE 16U
#define CONFIG_PAYLOAD_SIZE 34U
#define CONFIG_CRC_OFFSET 50U
#define CONFIG_COMMIT_OFFSET 52U
#define CONFIG_COMMIT_MARKER 0xA55AU

static ConfigFlashBackend_t s_backend;
static ConfigStoreStatus_t s_status;
static PersistentConfigV1_t s_current;
static uint32_t s_last_save_ms;
static bool s_has_saved;
static bool s_initialized;

static uint16_t Get16(const uint8_t *p) { return (uint16_t)p[0] | ((uint16_t)p[1] << 8U); }
static uint32_t Get32(const uint8_t *p) { return (uint32_t)Get16(p) | ((uint32_t)Get16(p + 2) << 16U); }
static void Put16(uint8_t *p, uint16_t v) { p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8U); }
static void Put32(uint8_t *p, uint32_t v) { Put16(p,(uint16_t)v); Put16(p+2,(uint16_t)(v>>16U)); }

void Config_GetFactoryDefaults(PersistentConfigV1_t *c)
{
    if (c == NULL) { return; }
    *c = (PersistentConfigV1_t){10U,100U,200U,980U,1U,0U,
        1450U,1500U,1550U,1U,0U,1000U,0U,50U,200U,100U,-10,10,0U};
}

bool ConfigStore_IsConfigValid(const PersistentConfigV1_t *c)
{
    return (c != NULL) && (c->sensor_period_ms >= 5U) && (c->sensor_period_ms <= 100U) &&
        (c->telemetry_period_ms >= 20U) && (c->telemetry_period_ms <= 5000U) &&
        (c->low_pass_alpha_milli >= 1U) && (c->low_pass_alpha_milli <= 1000U) &&
        (c->gyro_weight_milli >= 500U) && (c->gyro_weight_milli <= 999U) &&
        (c->log_level <= 4U) && (c->telemetry_enabled <= 1U) &&
        (c->servo_min_us == 1450U) && (c->servo_center_us == 1500U) &&
        (c->servo_max_us == 1550U) && (c->pid_axis <= 1U) &&
        (c->pid_direction <= 1U) && (c->kp_milli <= 50000U) &&
        (c->ki_milli <= 20000U) && (c->kd_milli <= 20000U) &&
        (c->derivative_alpha_milli <= 1000U) &&
        (c->deadband_cdeg >= 25U) && (c->deadband_cdeg <= 500U) &&
        (c->output_min_us >= -10) && (c->output_max_us <= 10) &&
        (c->output_min_us < c->output_max_us) && (c->integral_mode <= 2U);
}

static void EncodePayload(uint8_t *p, const PersistentConfigV1_t *c)
{
    Put16(p,c->sensor_period_ms); Put16(p+2,c->telemetry_period_ms);
    Put16(p+4,c->low_pass_alpha_milli); Put16(p+6,c->gyro_weight_milli);
    p[8]=c->log_level; p[9]=c->telemetry_enabled;
    Put16(p+10,c->servo_min_us); Put16(p+12,c->servo_center_us); Put16(p+14,c->servo_max_us);
    p[16]=c->pid_axis; p[17]=c->pid_direction; Put16(p+18,c->kp_milli);
    Put16(p+20,c->ki_milli); Put16(p+22,c->kd_milli);
    Put16(p+24,c->derivative_alpha_milli); Put16(p+26,c->deadband_cdeg);
    Put16(p+28,(uint16_t)c->output_min_us); Put16(p+30,(uint16_t)c->output_max_us);
    p[32]=c->integral_mode; p[33]=0U;
}

static void DecodePayload(const uint8_t *p, PersistentConfigV1_t *c)
{
    c->sensor_period_ms=Get16(p); c->telemetry_period_ms=Get16(p+2);
    c->low_pass_alpha_milli=Get16(p+4); c->gyro_weight_milli=Get16(p+6);
    c->log_level=p[8]; c->telemetry_enabled=p[9]; c->servo_min_us=Get16(p+10);
    c->servo_center_us=Get16(p+12); c->servo_max_us=Get16(p+14);
    c->pid_axis=p[16]; c->pid_direction=p[17]; c->kp_milli=Get16(p+18);
    c->ki_milli=Get16(p+20); c->kd_milli=Get16(p+22);
    c->derivative_alpha_milli=Get16(p+24); c->deadband_cdeg=Get16(p+26);
    c->output_min_us=(int16_t)Get16(p+28); c->output_max_us=(int16_t)Get16(p+30);
    c->integral_mode=p[32];
}

static bool ReadSlot(uint32_t address, PersistentConfigV1_t *c, uint32_t *generation)
{
    uint8_t r[CONFIG_RECORD_SIZE]; uint16_t schema;
    if (!s_backend.read(address,r,sizeof(r)) || Get32(r) != CONFIG_MAGIC ||
        Get16(r+6) != CONFIG_HEADER_SIZE || Get16(r+8) != CONFIG_PAYLOAD_SIZE ||
        Get16(r+CONFIG_COMMIT_OFFSET) != CONFIG_COMMIT_MARKER) {
        ++s_status.invalid_record_count; return false;
    }
    schema=Get16(r+4);
    if (schema != CONFIG_SCHEMA_VERSION) { ++s_status.unsupported_schema_count; return false; }
    if (Crc16CcittFalse_Calculate(r,CONFIG_CRC_OFFSET) != Get16(r+CONFIG_CRC_OFFSET)) {
        ++s_status.crc_error_count; return false;
    }
    DecodePayload(r+CONFIG_HEADER_SIZE,c);
    if (!ConfigStore_IsConfigValid(c)) { ++s_status.invalid_record_count; return false; }
    *generation=Get32(r+10); return true;
}

static bool IsNewer(uint32_t a, uint32_t b)
{ uint32_t delta=a-b; return (delta!=0U)&&(delta<0x80000000UL); }

bool ConfigStore_Init(const ConfigFlashBackend_t *backend, uint32_t now_ms,
                      PersistentConfigV1_t *loaded)
{
    PersistentConfigV1_t a,b; uint32_t ga=0U,gb=0U; bool va,vb;
    if ((backend==NULL)||(backend->read==NULL)||(backend->erase_page==NULL)||
        (backend->program==NULL)||(loaded==NULL)) return false;
    s_backend=*backend; s_status=(ConfigStoreStatus_t){0}; s_status.schema_version=CONFIG_SCHEMA_VERSION;
    va=ReadSlot(CONFIG_SLOT_A_ADDRESS,&a,&ga); vb=ReadSlot(CONFIG_SLOT_B_ADDRESS,&b,&gb);
    s_status.valid_slot_count=(uint8_t)((va?1U:0U)+(vb?1U:0U));
    if (va && (!vb || !IsNewer(gb,ga))) { s_current=a; s_status.loaded_from=CONFIG_SOURCE_SLOT_A; s_status.generation=ga; }
    else if (vb) { s_current=b; s_status.loaded_from=CONFIG_SOURCE_SLOT_B; s_status.generation=gb; }
    else { Config_GetFactoryDefaults(&s_current); s_status.loaded_from=CONFIG_SOURCE_DEFAULTS; }
    *loaded=s_current; s_last_save_ms=now_ms; s_has_saved=false; s_initialized=true; return true;
}

bool ConfigStore_Load(PersistentConfigV1_t *loaded)
{
    PersistentConfigV1_t a,b; uint32_t ga=0U,gb=0U; bool va,vb;
    if (!s_initialized || loaded==NULL) return false;
    va=ReadSlot(CONFIG_SLOT_A_ADDRESS,&a,&ga); vb=ReadSlot(CONFIG_SLOT_B_ADDRESS,&b,&gb);
    s_status.valid_slot_count=(uint8_t)((va?1U:0U)+(vb?1U:0U));
    if(va&&(!vb||!IsNewer(gb,ga))){s_current=a;s_status.loaded_from=CONFIG_SOURCE_SLOT_A;s_status.generation=ga;}
    else if(vb){s_current=b;s_status.loaded_from=CONFIG_SOURCE_SLOT_B;s_status.generation=gb;}
    else{Config_GetFactoryDefaults(&s_current);s_status.loaded_from=CONFIG_SOURCE_DEFAULTS;s_status.generation=0U;}
    s_status.dirty=false;*loaded=s_current;return true;
}

static void BuildRecord(uint8_t *r,const PersistentConfigV1_t *c,uint32_t generation)
{
    size_t i; for(i=0;i<CONFIG_RECORD_SIZE;i++) r[i]=0xFFU;
    Put32(r,CONFIG_MAGIC); Put16(r+4,CONFIG_SCHEMA_VERSION); Put16(r+6,CONFIG_HEADER_SIZE);
    Put16(r+8,CONFIG_PAYLOAD_SIZE); Put32(r+10,generation); Put16(r+14,0U);
    EncodePayload(r+CONFIG_HEADER_SIZE,c); Put16(r+CONFIG_CRC_OFFSET,Crc16CcittFalse_Calculate(r,CONFIG_CRC_OFFSET));
}

ConfigSaveStatus_t ConfigStore_Save(const PersistentConfigV1_t *c,uint32_t now_ms,bool safe)
{
    uint8_t r[CONFIG_RECORD_SIZE],verify[CONFIG_RECORD_SIZE]; uint32_t target,generation;
    uint32_t started_ms;
    if (!s_initialized || !ConfigStore_IsConfigValid(c)) return CONFIG_SAVE_INVALID;
    if (!safe) return CONFIG_SAVE_BUSY;
    if (s_has_saved && (uint32_t)(now_ms-s_last_save_ms)<CONFIG_SAVE_MIN_INTERVAL_MS) {
        ++s_status.save_rate_limited_count; return CONFIG_SAVE_RATE_LIMITED;
    }
    started_ms=(s_backend.time_ms!=NULL)?s_backend.time_ms():now_ms;
    target=(s_status.loaded_from==CONFIG_SOURCE_SLOT_A)?CONFIG_SLOT_B_ADDRESS:CONFIG_SLOT_A_ADDRESS;
    generation=s_status.generation+1U; BuildRecord(r,c,generation);
    if (!s_backend.erase_page(target)) return s_status.last_save_status=CONFIG_SAVE_ERASE_FAILED;
    if (!s_backend.program(target,r,CONFIG_COMMIT_OFFSET)) return s_status.last_save_status=CONFIG_SAVE_PROGRAM_FAILED;
    if (!s_backend.read(target,verify,CONFIG_COMMIT_OFFSET) ||
        Crc16CcittFalse_Calculate(verify,CONFIG_CRC_OFFSET)!=Get16(verify+CONFIG_CRC_OFFSET))
        return s_status.last_save_status=CONFIG_SAVE_VERIFY_FAILED;
    Put16(r+CONFIG_COMMIT_OFFSET,CONFIG_COMMIT_MARKER);
    if (!s_backend.program(target+CONFIG_COMMIT_OFFSET,r+CONFIG_COMMIT_OFFSET,2U) ||
        !s_backend.read(target,verify,sizeof(verify)) || Get16(verify+CONFIG_COMMIT_OFFSET)!=CONFIG_COMMIT_MARKER)
        return s_status.last_save_status=CONFIG_SAVE_VERIFY_FAILED;
    s_current=*c; s_status.generation=generation; s_status.loaded_from=(target==CONFIG_SLOT_A_ADDRESS)?CONFIG_SOURCE_SLOT_A:CONFIG_SOURCE_SLOT_B;
    s_status.valid_slot_count=(s_status.valid_slot_count<2U)?(uint8_t)(s_status.valid_slot_count+1U):2U;
    s_status.last_save_status=CONFIG_SAVE_OK; ++s_status.save_count; s_status.dirty=false;
    s_status.last_save_duration_ms=(s_backend.time_ms!=NULL)?
        (uint32_t)(s_backend.time_ms()-started_ms):0U;
    s_last_save_ms=now_ms; s_has_saved=true; return CONFIG_SAVE_OK;
}

ConfigSaveStatus_t ConfigStore_FactoryReset(uint32_t now_ms,bool safe,PersistentConfigV1_t *defaults)
{
    uint32_t started_ms;
    if (!s_initialized || defaults==NULL) return CONFIG_SAVE_INVALID;
    if (!safe) return CONFIG_SAVE_BUSY;
    started_ms=(s_backend.time_ms!=NULL)?s_backend.time_ms():now_ms;
    if (!s_backend.erase_page(CONFIG_SLOT_A_ADDRESS)||!s_backend.erase_page(CONFIG_SLOT_B_ADDRESS))
        return s_status.last_save_status=CONFIG_SAVE_ERASE_FAILED;
    Config_GetFactoryDefaults(&s_current); *defaults=s_current; s_status.loaded_from=CONFIG_SOURCE_DEFAULTS;
    s_status.generation=0U; s_status.valid_slot_count=0U; s_status.dirty=false;
    s_status.last_save_status=CONFIG_SAVE_OK; ++s_status.factory_reset_count;
    s_status.last_save_duration_ms=(s_backend.time_ms!=NULL)?
        (uint32_t)(s_backend.time_ms()-started_ms):0U;
    s_last_save_ms=now_ms; s_has_saved=true; return CONFIG_SAVE_OK;
}

void ConfigStore_MarkDirty(void) { if (s_initialized) s_status.dirty=true; }
bool ConfigStore_GetStatus(ConfigStoreStatus_t *status) { if(!s_initialized||status==NULL)return false; *status=s_status; return true; }
