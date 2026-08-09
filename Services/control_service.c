#include "control_service.h"

#include <math.h>
#include <stddef.h>

#define CONTROL_CENTER_PULSE_US 1500U
#define CONTROL_SAFE_MIN_PULSE_US 1450U
#define CONTROL_SAFE_MAX_PULSE_US 1550U

static const PidControllerConfig_t s_default_pid_config = {
    1.0F, 0.0F, 0.0F,
    -10.0F, 10.0F,
    -10.0F, 10.0F,
    0.20F, 0.005F, 0.030F,
    PID_INTEGRAL_MODE_DISABLED, 0.99F};

static PidController_t s_pid;
static ControlConfig_t s_config;
static ControlStatus_t s_status;
static ActuatorOwner_t s_request_owner;
static uint32_t s_last_motion_sequence;
static uint32_t s_last_motion_timestamp_ms;
static uint8_t s_warmup_samples;
static bool s_has_motion;
static bool s_initialized;

static int32_t AxisAngle(const MotionFrame_t *motion, ControlAxis_t axis)
{
    return (axis == CONTROL_AXIS_ROLL) ? motion->attitude.roll_cdeg
                                       : motion->attitude.pitch_cdeg;
}

static bool IsOwnerAllowed(ActuatorOwner_t owner)
{
    return (owner == ACTUATOR_OWNER_SERIAL) ||
           (owner == ACTUATOR_OWNER_MQTT) ||
           (owner == ACTUATOR_OWNER_LOCAL);
}

static void ResetOutputState(void)
{
    s_status.active = false;
    s_status.saturated = false;
    s_status.in_deadband = true;
    s_status.effective_error_cdeg = 0;
    s_status.p_term_milli = 0;
    s_status.i_term_milli = 0;
    s_status.d_term_milli = 0;
    s_status.output_us = 0;
    s_status.requested_pulse_us = CONTROL_CENTER_PULSE_US;
}

static void EnterSafeState(ControlFault_t fault)
{
    if (s_status.mode != CONTROL_MODE_DISABLED)
    {
        (void)ActuatorService_EmergencyStop(ACTUATOR_OWNER_LOCAL);
        ++s_status.fault_count;
    }
    s_status.mode = CONTROL_MODE_DISABLED;
    s_status.enabled = false;
    s_status.last_fault = fault;
    s_request_owner = ACTUATOR_OWNER_NONE;
    s_warmup_samples = 0U;
    s_has_motion = false;
    ResetOutputState();
    (void)PidController_Reset(&s_pid, 0.0F);
}

bool ControlService_Init(uint32_t now_ms)
{
    (void)now_ms;
    s_config.pid = s_default_pid_config;
    s_config.axis = CONTROL_AXIS_ROLL;
    s_config.direction = CONTROL_DIRECTION_NORMAL;
    s_config.deadband_cdeg = 100U;
    s_status = (ControlStatus_t){0};
    s_status.axis = s_config.axis;
    s_status.direction = s_config.direction;
    s_status.integral_mode = s_config.pid.integral_mode;
    s_status.deadband_cdeg = s_config.deadband_cdeg;
    s_status.requested_pulse_us = CONTROL_CENTER_PULSE_US;
    s_status.actual_pulse_us = CONTROL_CENTER_PULSE_US;
    s_request_owner = ACTUATOR_OWNER_NONE;
    s_last_motion_sequence = 0U;
    s_last_motion_timestamp_ms = 0U;
    s_warmup_samples = 0U;
    s_has_motion = false;
    s_initialized = PidController_Init(&s_pid, &s_config.pid) &&
                    PidController_Reset(&s_pid, 0.0F);
    return s_initialized;
}

ControlResult_t ControlService_Enable(ActuatorOwner_t owner,
                                      ControlAxis_t axis,
                                      const MotionFrame_t *motion,
                                      uint32_t now_ms,
                                      bool app_running,
                                      bool sensor_online)
{
    ActuatorResult_t actuator_result;
    ActuatorStatus_t actuator;

    if (!s_initialized || !IsOwnerAllowed(owner) ||
        (axis > CONTROL_AXIS_PITCH) || (motion == NULL))
    {
        return CONTROL_RESULT_INVALID_ARGUMENT;
    }
    if (s_status.enabled) { return CONTROL_RESULT_BUSY; }
    if (!app_running || !sensor_online || !motion->valid || !motion->calibrated ||
        ((uint32_t)(now_ms - motion->timestamp_ms) > CONTROL_MOTION_TIMEOUT_MS) ||
        ((motion->status_flags & MOTION_SAMPLE_FLAG_STALE) != 0U) ||
        !ActuatorService_GetCurrentStatus(&actuator) || !actuator.armed)
    {
        return CONTROL_RESULT_NOT_READY;
    }
    actuator_result = ActuatorService_BeginAttitudeControl(owner);
    if (actuator_result != ACTUATOR_RESULT_OK)
    {
        return CONTROL_RESULT_ACTUATOR_ERROR;
    }
    s_config.axis = axis;
    s_status.axis = axis;
    s_status.zero_angle_cdeg = AxisAngle(motion, axis);
    s_status.measured_angle_cdeg = s_status.zero_angle_cdeg;
    s_status.relative_angle_cdeg = 0;
    s_status.mode = CONTROL_MODE_PID_ATTITUDE;
    s_status.enabled = true;
    s_status.last_fault = CONTROL_FAULT_NONE;
    s_request_owner = owner;
    s_last_motion_sequence = motion->sequence;
    s_last_motion_timestamp_ms = motion->timestamp_ms;
    s_warmup_samples = 0U;
    s_has_motion = true;
    ResetOutputState();
    (void)PidController_Reset(&s_pid, 0.0F);
    return CONTROL_RESULT_OK;
}

ControlResult_t ControlService_Disable(ActuatorOwner_t owner)
{
    if (!s_initialized || !IsOwnerAllowed(owner))
    {
        return CONTROL_RESULT_INVALID_ARGUMENT;
    }
    if (!s_status.enabled) { return CONTROL_RESULT_OK; }
    if (owner != s_request_owner) { return CONTROL_RESULT_BUSY; }
    if (ActuatorService_Disarm(ACTUATOR_OWNER_CONTROL_LOOP) != ACTUATOR_RESULT_OK)
    {
        return CONTROL_RESULT_ACTUATOR_ERROR;
    }
    s_status.mode = CONTROL_MODE_DISABLED;
    s_status.enabled = false;
    s_status.last_fault = CONTROL_FAULT_NONE;
    s_request_owner = ACTUATOR_OWNER_NONE;
    s_warmup_samples = 0U;
    ResetOutputState();
    (void)PidController_Reset(&s_pid, 0.0F);
    return CONTROL_RESULT_OK;
}

ControlResult_t ControlService_SetZero(ActuatorOwner_t owner,
                                       const MotionFrame_t *motion,
                                       uint32_t now_ms)
{
    if (!s_initialized || !IsOwnerAllowed(owner) || (motion == NULL))
    {
        return CONTROL_RESULT_INVALID_ARGUMENT;
    }
    if (s_status.enabled && (owner != s_request_owner)) { return CONTROL_RESULT_BUSY; }
    if (!motion->valid || !motion->calibrated ||
        ((uint32_t)(now_ms - motion->timestamp_ms) > CONTROL_MOTION_TIMEOUT_MS))
    {
        return CONTROL_RESULT_NOT_READY;
    }
    s_status.zero_angle_cdeg = AxisAngle(motion, s_config.axis);
    s_status.measured_angle_cdeg = s_status.zero_angle_cdeg;
    s_status.relative_angle_cdeg = 0;
    s_last_motion_sequence = motion->sequence;
    s_last_motion_timestamp_ms = motion->timestamp_ms;
    s_warmup_samples = 0U;
    ResetOutputState();
    (void)PidController_Reset(&s_pid, 0.0F);
    if (s_status.enabled &&
        (ActuatorService_SetControlPulse(CONTROL_CENTER_PULSE_US) !=
         ACTUATOR_RESULT_OK))
    {
        EnterSafeState(CONTROL_FAULT_ACTUATOR);
        return CONTROL_RESULT_ACTUATOR_ERROR;
    }
    return CONTROL_RESULT_OK;
}

ControlResult_t ControlService_SetAxis(ControlAxis_t axis)
{
    if (!s_initialized || (axis > CONTROL_AXIS_PITCH))
    {
        return CONTROL_RESULT_INVALID_ARGUMENT;
    }
    if (s_status.enabled) { return CONTROL_RESULT_BUSY; }
    s_config.axis = axis;
    s_status.axis = axis;
    return CONTROL_RESULT_OK;
}

ControlResult_t ControlService_SetDirection(ControlDirection_t direction)
{
    if (!s_initialized || (direction > CONTROL_DIRECTION_REVERSE))
    {
        return CONTROL_RESULT_INVALID_ARGUMENT;
    }
    if (s_status.enabled) { return CONTROL_RESULT_BUSY; }
    s_config.direction = direction;
    s_status.direction = direction;
    return CONTROL_RESULT_OK;
}

ControlResult_t ControlService_SetPidConfig(const PidControllerConfig_t *config)
{
    if (!s_initialized || !PidController_IsConfigValid(config) ||
        (config->kp > 50.0F) || (config->ki > 20.0F) ||
        (config->kd > 20.0F) ||
        (config->output_min < -50.0F) || (config->output_max > 50.0F))
    {
        return CONTROL_RESULT_INVALID_ARGUMENT;
    }
    if (s_status.enabled) { return CONTROL_RESULT_BUSY; }
    if (!PidController_SetConfig(&s_pid, config))
    {
        return CONTROL_RESULT_INVALID_ARGUMENT;
    }
    s_config.pid = *config;
    s_status.integral_mode = config->integral_mode;
    return CONTROL_RESULT_OK;
}

ControlResult_t ControlService_SetDeadband(uint16_t deadband_cdeg)
{
    if (!s_initialized || (deadband_cdeg < 25U) || (deadband_cdeg > 500U))
    {
        return CONTROL_RESULT_INVALID_ARGUMENT;
    }
    if (s_status.enabled) { return CONTROL_RESULT_BUSY; }
    s_config.deadband_cdeg = deadband_cdeg;
    s_status.deadband_cdeg = deadband_cdeg;
    return CONTROL_RESULT_OK;
}

void ControlService_NotifyEmergencyStop(void)
{
    if (!s_initialized) { return; }
    s_status.mode = CONTROL_MODE_DISABLED;
    s_status.enabled = false;
    s_request_owner = ACTUATOR_OWNER_NONE;
    s_warmup_samples = 0U;
    ResetOutputState();
    (void)PidController_Reset(&s_pid, 0.0F);
}

void ControlService_Update(const MotionFrame_t *motion,
                           uint32_t now_ms,
                           bool app_running,
                           bool sensor_online,
                           bool app_fault)
{
    ActuatorStatus_t actuator;
    PidControllerOutput_t output;
    uint32_t dt_ms;
    int32_t relative;
    int32_t effective;
    float error_deg;
    float relative_deg;
    int32_t signed_offset;
    int32_t requested;
    bool deadband;

    if (!s_initialized || !s_status.enabled) { return; }
    if (app_fault)
    {
        EnterSafeState(CONTROL_FAULT_APP_FAULT);
        return;
    }
    if (!sensor_online || (motion == NULL) || !motion->valid)
    {
        EnterSafeState(CONTROL_FAULT_SENSOR_OFFLINE);
        return;
    }
    /* 传感器掉线会先让应用进入DEGRADED；应保留更具体的传感器故障，
     * 仅在传感器仍在线时把非RUNNING状态归类为应用故障。 */
    if (!app_running)
    {
        EnterSafeState(CONTROL_FAULT_APP_FAULT);
        return;
    }
    if (!motion->calibrated)
    {
        EnterSafeState(CONTROL_FAULT_NOT_CALIBRATED);
        return;
    }
    if (((uint32_t)(now_ms - motion->timestamp_ms) > CONTROL_MOTION_TIMEOUT_MS) ||
        ((motion->status_flags & MOTION_SAMPLE_FLAG_STALE) != 0U))
    {
        ++s_status.stale_motion_count;
        EnterSafeState(CONTROL_FAULT_STALE_MOTION);
        return;
    }
    if (!ActuatorService_GetCurrentStatus(&actuator) || !actuator.armed ||
        (actuator.owner != ACTUATOR_OWNER_CONTROL_LOOP))
    {
        EnterSafeState(CONTROL_FAULT_ACTUATOR);
        return;
    }
    if (motion->sequence == s_last_motion_sequence) { return; }

    dt_ms = motion->timestamp_ms - s_last_motion_timestamp_ms;
    s_last_motion_sequence = motion->sequence;
    s_last_motion_timestamp_ms = motion->timestamp_ms;
    s_status.motion_age_ms = now_ms - motion->timestamp_ms;
    s_status.measured_angle_cdeg = AxisAngle(motion, s_config.axis);
    relative = s_status.measured_angle_cdeg - s_status.zero_angle_cdeg;
    s_status.relative_angle_cdeg = relative;

    if ((dt_ms < 5U) || (dt_ms > 30U))
    {
        ++s_status.invalid_dt_count;
        s_status.last_fault = CONTROL_FAULT_INVALID_DT;
        return;
    }
    if (s_warmup_samples < CONTROL_WARMUP_SAMPLE_COUNT)
    {
        ++s_warmup_samples;
        (void)PidController_Reset(&s_pid, (float)relative / 100.0F);
        if (s_warmup_samples == CONTROL_WARMUP_SAMPLE_COUNT)
        {
            s_status.active = true;
        }
        return;
    }

    deadband = (relative >= -(int32_t)s_config.deadband_cdeg) &&
               (relative <= (int32_t)s_config.deadband_cdeg);
    if (deadband != s_status.in_deadband)
    {
        if (deadband) { ++s_status.deadband_entry_count; }
        else { ++s_status.deadband_exit_count; }
        (void)PidController_Reset(&s_pid, (float)relative / 100.0F);
    }
    s_status.in_deadband = deadband;
    effective = deadband ? 0 : relative;
    s_status.effective_error_cdeg = effective;
    relative_deg = (float)relative / 100.0F;
    error_deg = (float)effective / 100.0F;
    if (!isfinite(relative_deg) || !isfinite(error_deg))
    {
        ++s_status.nonfinite_input_count;
        EnterSafeState(CONTROL_FAULT_NONFINITE);
        return;
    }
    if (deadband)
    {
        (void)PidController_Reset(&s_pid, relative_deg);
        output = (PidControllerOutput_t){0};
    }
    else if (!PidController_Update(&s_pid,
                                   error_deg,
                                   relative_deg,
                                   (float)dt_ms / 1000.0F,
                                   &output))
    {
        ++s_status.nonfinite_input_count;
        EnterSafeState(CONTROL_FAULT_NONFINITE);
        return;
    }

    if (output.integrator_limited) { ++s_status.integrator_saturation_count; }
    s_status.saturated = output.saturated;
    s_status.p_term_milli = (int32_t)lroundf(output.p_term * 1000.0F);
    s_status.i_term_milli = (int32_t)lroundf(output.i_term * 1000.0F);
    s_status.d_term_milli = (int32_t)lroundf(output.d_term * 1000.0F);
    s_status.output_us = (int16_t)lroundf(output.output);
    signed_offset = (s_config.direction == CONTROL_DIRECTION_NORMAL)
                        ? (int32_t)s_status.output_us
                        : -(int32_t)s_status.output_us;
    requested = (int32_t)CONTROL_CENTER_PULSE_US + signed_offset;
    if (requested < (int32_t)CONTROL_SAFE_MIN_PULSE_US)
    {
        requested = CONTROL_SAFE_MIN_PULSE_US;
        ++s_status.target_limit_count;
    }
    else if (requested > (int32_t)CONTROL_SAFE_MAX_PULSE_US)
    {
        requested = CONTROL_SAFE_MAX_PULSE_US;
        ++s_status.target_limit_count;
    }
    s_status.requested_pulse_us = (uint16_t)requested;
    if (ActuatorService_SetControlPulse(s_status.requested_pulse_us) !=
        ACTUATOR_RESULT_OK)
    {
        EnterSafeState(CONTROL_FAULT_ACTUATOR);
        return;
    }
    ++s_status.update_count;
    s_status.last_fault = CONTROL_FAULT_NONE;
}

bool ControlService_GetConfig(ControlConfig_t *config)
{
    if (!s_initialized || (config == NULL)) { return false; }
    *config = s_config;
    return true;
}

bool ControlService_GetStatus(uint32_t now_ms, ControlStatus_t *status)
{
    ActuatorStatus_t actuator;
    if (!s_initialized || (status == NULL)) { return false; }
    s_status.kp_milli = (int32_t)lroundf(s_config.pid.kp * 1000.0F);
    s_status.ki_milli = (int32_t)lroundf(s_config.pid.ki * 1000.0F);
    s_status.kd_milli = (int32_t)lroundf(s_config.pid.kd * 1000.0F);
    if (s_has_motion) { s_status.motion_age_ms = now_ms - s_last_motion_timestamp_ms; }
    if (ActuatorService_GetCurrentStatus(&actuator))
    {
        s_status.actual_pulse_us = actuator.current_pulse_us;
    }
    *status = s_status;
    return true;
}
