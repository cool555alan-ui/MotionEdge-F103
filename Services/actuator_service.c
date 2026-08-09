#include "actuator_service.h"

#include <stddef.h>

#include "bsp_pwm.h"

static const ServoActuatorConfig_t s_default_config = {
    /* SG90实机确认1400~1600 us可安全动作，正式窗口每侧再留50 us裕量。 */
    1450U, 1500U, 1550U, -4500, 0, 4500, 500U};
static ServoActuator_t s_servo;
static ActuatorMode_t s_mode;
static ActuatorOwner_t s_owner;
static uint32_t s_now_ms;
static uint32_t s_last_command_ms;
static uint32_t s_timeout_count;
static uint32_t s_limit_count;
static uint32_t s_fault_count;
static uint32_t s_estop_count;
static bool s_armed;
static bool s_timeout_latched;
static bool s_initialized;

static bool IsOwnerValid(ActuatorOwner_t owner)
{
    return (owner > ACTUATOR_OWNER_NONE) &&
           (owner <= ACTUATOR_OWNER_CONTROL_LOOP);
}

static bool OwnerMatches(ActuatorOwner_t owner)
{
    return IsOwnerValid(owner) && (owner == s_owner);
}

static void EnterFault(void)
{
    if (s_servo.state != SERVO_STATE_FAULT) { ++s_fault_count; }
    (void)BspPwm_Stop();
    s_servo.state = SERVO_STATE_FAULT;
    s_mode = ACTUATOR_MODE_DISABLED;
    s_owner = ACTUATOR_OWNER_NONE;
    s_armed = false;
}

bool ActuatorService_Init(uint32_t now_ms)
{
    s_mode = ACTUATOR_MODE_DISABLED;
    s_owner = ACTUATOR_OWNER_NONE;
    s_now_ms = now_ms;
    s_last_command_ms = now_ms;
    s_timeout_count = 0U;
    s_limit_count = 0U;
    s_fault_count = 0U;
    s_estop_count = 0U;
    s_armed = false;
    s_timeout_latched = false;
    s_initialized = ServoActuator_Init(&s_servo, &s_default_config, now_ms) &&
                    (BspPwm_Init() == BSP_PWM_OK) &&
                    (BspPwm_SetPulseUs(s_default_config.pulse_center_us) ==
                     BSP_PWM_OK);
    if (!s_initialized)
    {
        s_servo.state = SERVO_STATE_FAULT;
        ++s_fault_count;
    }
    return s_initialized;
}

ActuatorResult_t ActuatorService_Arm(ActuatorOwner_t owner)
{
    if (!s_initialized || (s_servo.state == SERVO_STATE_FAULT))
    {
        return ACTUATOR_RESULT_FAULT;
    }
    if (!IsOwnerValid(owner)) { return ACTUATOR_RESULT_INVALID_ARGUMENT; }
    if (s_armed)
    {
        return OwnerMatches(owner) ? ACTUATOR_RESULT_OK
                                   : ACTUATOR_RESULT_OWNER_CONFLICT;
    }
    s_servo.current_pulse_us = s_servo.config.pulse_center_us;
    s_servo.target_pulse_us = s_servo.config.pulse_center_us;
    s_servo.last_update_ms = s_now_ms;
    s_servo.state = SERVO_STATE_ARMING;
    if ((BspPwm_SetPulseUs(s_servo.config.pulse_center_us) != BSP_PWM_OK) ||
        (BspPwm_Start() != BSP_PWM_OK))
    {
        EnterFault();
        return ACTUATOR_RESULT_HARDWARE;
    }
    s_owner = owner;
    s_mode = ACTUATOR_MODE_MANUAL;
    s_armed = true;
    s_timeout_latched = false;
    s_last_command_ms = s_now_ms;
    s_servo.state = SERVO_STATE_READY;
    return ACTUATOR_RESULT_OK;
}

ActuatorResult_t ActuatorService_Disarm(ActuatorOwner_t owner)
{
    if (!IsOwnerValid(owner)) { return ACTUATOR_RESULT_INVALID_ARGUMENT; }
    if (BspPwm_Stop() != BSP_PWM_OK)
    {
        EnterFault();
        return ACTUATOR_RESULT_HARDWARE;
    }
    s_mode = ACTUATOR_MODE_DISABLED;
    s_owner = ACTUATOR_OWNER_NONE;
    s_armed = false;
    s_timeout_latched = false;
    s_servo.state = SERVO_STATE_DISABLED;
    return ACTUATOR_RESULT_OK;
}

ActuatorResult_t ActuatorService_SetTargetAngle(ActuatorOwner_t owner,
                                                int16_t angle_cdeg)
{
    bool limited;

    if (!s_armed) { return ACTUATOR_RESULT_NOT_ARMED; }
    if (!OwnerMatches(owner)) { return ACTUATOR_RESULT_OWNER_CONFLICT; }
    if (s_mode != ACTUATOR_MODE_MANUAL) { return ACTUATOR_RESULT_UNSUPPORTED; }
    if (!ServoActuator_SetTargetAngle(&s_servo, angle_cdeg, &limited))
    {
        return ACTUATOR_RESULT_INVALID_ARGUMENT;
    }
    if (limited) { ++s_limit_count; }
    s_last_command_ms = s_now_ms;
    s_timeout_latched = false;
    return ACTUATOR_RESULT_OK;
}

ActuatorResult_t ActuatorService_SetRawPulse(ActuatorOwner_t owner,
                                             uint16_t pulse_us)
{
    bool limited;

    if (!s_armed) { return ACTUATOR_RESULT_NOT_ARMED; }
    if (!OwnerMatches(owner)) { return ACTUATOR_RESULT_OWNER_CONFLICT; }
    if (s_mode != ACTUATOR_MODE_MANUAL) { return ACTUATOR_RESULT_UNSUPPORTED; }
    if (!ServoActuator_SetTargetPulse(&s_servo, pulse_us, &limited))
    {
        return ACTUATOR_RESULT_INVALID_ARGUMENT;
    }
    if (limited) { ++s_limit_count; }
    s_last_command_ms = s_now_ms;
    s_timeout_latched = false;
    return ACTUATOR_RESULT_OK;
}

ActuatorResult_t ActuatorService_Center(ActuatorOwner_t owner)
{
    return ActuatorService_SetRawPulse(owner, s_servo.config.pulse_center_us);
}

ActuatorResult_t ActuatorService_EmergencyStop(ActuatorOwner_t owner)
{
    if (!IsOwnerValid(owner)) { return ACTUATOR_RESULT_INVALID_ARGUMENT; }
    ++s_estop_count;
    /* 未知机械负载下采用最保守策略：立即停止 PWM，之后必须重新 Arm。 */
    if (BspPwm_Stop() != BSP_PWM_OK)
    {
        EnterFault();
        return ACTUATOR_RESULT_HARDWARE;
    }
    s_mode = ACTUATOR_MODE_DISABLED;
    s_owner = ACTUATOR_OWNER_NONE;
    s_armed = false;
    s_timeout_latched = false;
    s_servo.state = SERVO_STATE_DISABLED;
    return ACTUATOR_RESULT_OK;
}

void ActuatorService_Update(uint32_t now_ms,
                            bool app_fault,
                            bool motion_online,
                            bool motion_stale)
{
    uint16_t pulse;

    s_now_ms = now_ms;
    if (!s_initialized) { return; }
    if (app_fault)
    {
        EnterFault();
        return;
    }
    if ((s_mode == ACTUATOR_MODE_ATTITUDE_HOLD) &&
        (!motion_online || motion_stale))
    {
        (void)ActuatorService_EmergencyStop(ACTUATOR_OWNER_LOCAL);
        return;
    }
    if (!s_armed) { return; }
    if ((s_mode == ACTUATOR_MODE_MANUAL) &&
        ((uint32_t)(now_ms - s_last_command_ms) >= ACTUATOR_COMMAND_TIMEOUT_MS) &&
        !s_timeout_latched)
    {
        s_servo.target_pulse_us = s_servo.config.pulse_center_us;
        s_timeout_latched = true;
        ++s_timeout_count;
    }
    pulse = ServoActuator_Update(&s_servo, now_ms);
    if (BspPwm_SetPulseUs(pulse) != BSP_PWM_OK) { EnterFault(); }
}

bool ActuatorService_GetStatus(uint32_t now_ms, ActuatorStatus_t *status)
{
    uint16_t safe_min;
    uint16_t safe_max;

    if (!s_initialized || (status == NULL)) { return false; }
    safe_min = (s_servo.config.pulse_min_us < s_servo.config.pulse_max_us)
                   ? s_servo.config.pulse_min_us
                   : s_servo.config.pulse_max_us;
    safe_max = (s_servo.config.pulse_min_us > s_servo.config.pulse_max_us)
                   ? s_servo.config.pulse_min_us
                   : s_servo.config.pulse_max_us;
    status->mode = s_mode;
    status->state = s_servo.state;
    status->armed = s_armed;
    status->owner = s_owner;
    (void)ServoActuator_MapPulseToAngle(
        &s_servo.config, s_servo.target_pulse_us, &status->target_angle_cdeg);
    (void)ServoActuator_MapPulseToAngle(
        &s_servo.config, s_servo.current_pulse_us, &status->current_angle_cdeg);
    status->target_pulse_us = s_servo.target_pulse_us;
    status->current_pulse_us = s_servo.current_pulse_us;
    status->safe_min_us = safe_min;
    status->safe_max_us = safe_max;
    status->command_age_ms = now_ms - s_last_command_ms;
    status->timeout_count = s_timeout_count;
    status->limit_count = s_limit_count;
    status->fault_count = s_fault_count;
    status->estop_count = s_estop_count;
    return true;
}

bool ActuatorService_GetCurrentStatus(ActuatorStatus_t *status)
{
    return ActuatorService_GetStatus(s_now_ms, status);
}
