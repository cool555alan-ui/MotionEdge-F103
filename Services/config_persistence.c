#include "config_persistence.h"

#include "actuator_service.h"
#include "bsp_flash.h"
#include "config_service.h"
#include "control_service.h"

static void Capture(PersistentConfigV1_t *p)
{
    RuntimeConfig_t r; ControlConfig_t c;
    Config_GetFactoryDefaults(p);
    if(ConfigService_Get(&r)){p->sensor_period_ms=r.sensor_sample_period_ms;p->telemetry_period_ms=r.telemetry_period_ms;p->low_pass_alpha_milli=r.low_pass_alpha_milli;p->gyro_weight_milli=r.complementary_gyro_weight_milli;p->log_level=r.log_level;p->telemetry_enabled=r.telemetry_enabled?1U:0U;}
    if(ControlService_GetConfig(&c)){p->pid_axis=(uint8_t)c.axis;p->pid_direction=(uint8_t)c.direction;p->kp_milli=(uint16_t)(c.pid.kp*1000.0F);p->ki_milli=(uint16_t)(c.pid.ki*1000.0F);p->kd_milli=(uint16_t)(c.pid.kd*1000.0F);p->derivative_alpha_milli=(uint16_t)(c.pid.derivative_alpha*1000.0F);p->deadband_cdeg=c.deadband_cdeg;p->output_min_us=(int16_t)c.pid.output_min;p->output_max_us=(int16_t)c.pid.output_max;p->integral_mode=(uint8_t)c.pid.integral_mode;}
}
static bool Apply(const PersistentConfigV1_t *p)
{
    RuntimeConfig_t r; ControlConfig_t c;
    if(!ConfigStore_IsConfigValid(p)||!ConfigService_Get(&r)||!ControlService_GetConfig(&c))return false;
    r.sensor_sample_period_ms=p->sensor_period_ms;r.telemetry_period_ms=p->telemetry_period_ms;r.low_pass_alpha_milli=p->low_pass_alpha_milli;r.complementary_gyro_weight_milli=p->gyro_weight_milli;r.log_level=p->log_level;r.telemetry_enabled=p->telemetry_enabled!=0U;
    c.axis=(ControlAxis_t)p->pid_axis;c.direction=(ControlDirection_t)p->pid_direction;c.deadband_cdeg=p->deadband_cdeg;c.pid.kp=(float)p->kp_milli/1000.0F;c.pid.ki=(float)p->ki_milli/1000.0F;c.pid.kd=(float)p->kd_milli/1000.0F;c.pid.derivative_alpha=(float)p->derivative_alpha_milli/1000.0F;c.pid.output_min=(float)p->output_min_us;c.pid.output_max=(float)p->output_max_us;c.pid.integrator_min=c.pid.output_min;c.pid.integrator_max=c.pid.output_max;c.pid.integral_mode=(PidIntegralMode_t)p->integral_mode;
    return ConfigService_Set(&r)&&ControlService_SetAxis(c.axis)==CONTROL_RESULT_OK&&ControlService_SetDirection(c.direction)==CONTROL_RESULT_OK&&ControlService_SetPidConfig(&c.pid)==CONTROL_RESULT_OK&&ControlService_SetDeadband(c.deadband_cdeg)==CONTROL_RESULT_OK;
}
static bool Safe(void)
{
    ActuatorStatus_t a; ControlStatus_t c;
    return ActuatorService_GetCurrentStatus(&a)&&ControlService_GetStatus(0U,&c)&&!a.armed&&a.owner==ACTUATOR_OWNER_NONE&&!c.enabled;
}
bool ConfigPersistence_Init(uint32_t now_ms)
{
    PersistentConfigV1_t p; return ConfigStore_Init(BspFlash_GetConfigBackend(),now_ms,&p)&&Apply(&p);
}
ConfigSaveStatus_t ConfigPersistence_Save(uint32_t now_ms)
{
    PersistentConfigV1_t p; Capture(&p); return ConfigStore_Save(&p,now_ms,Safe());
}
ConfigSaveStatus_t ConfigPersistence_Load(void)
{
    PersistentConfigV1_t p; if(!Safe())return CONFIG_SAVE_BUSY; return (ConfigStore_Load(&p)&&Apply(&p))?CONFIG_SAVE_OK:CONFIG_SAVE_INVALID;
}
ConfigSaveStatus_t ConfigPersistence_FactoryReset(uint32_t now_ms)
{
    PersistentConfigV1_t p; ConfigSaveStatus_t result=ConfigStore_FactoryReset(now_ms,Safe(),&p); return (result==CONFIG_SAVE_OK&&!Apply(&p))?CONFIG_SAVE_INVALID:result;
}
