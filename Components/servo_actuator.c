#include "servo_actuator.h"

#include <limits.h>
#include <stddef.h>

#define SERVO_MAX_UPDATE_DT_MS 100U

static int32_t Interpolate(int32_t input,
                           int32_t input_start,
                           int32_t input_end,
                           int32_t output_start,
                           int32_t output_end)
{
    int64_t numerator = (int64_t)(input - input_start) *
                        (int64_t)(output_end - output_start);
    int64_t denominator = (int64_t)input_end - input_start;

    return output_start + (int32_t)(numerator / denominator);
}

bool ServoActuator_IsConfigValid(const ServoActuatorConfig_t *config)
{
    if ((config == NULL) || (config->pulse_min_us == config->pulse_center_us) ||
        (config->pulse_center_us == config->pulse_max_us) ||
        (config->angle_min_cdeg >= config->angle_center_cdeg) ||
        (config->angle_center_cdeg >= config->angle_max_cdeg) ||
        (config->max_slew_us_per_s == 0U))
    {
        return false;
    }
    /* Pulse 端点可正向或反向，但中位必须位于两个端点之间。 */
    return ((config->pulse_min_us < config->pulse_center_us) &&
            (config->pulse_center_us < config->pulse_max_us)) ||
           ((config->pulse_min_us > config->pulse_center_us) &&
            (config->pulse_center_us > config->pulse_max_us));
}

bool ServoActuator_MapAngleToPulse(const ServoActuatorConfig_t *config,
                                  int16_t angle_cdeg,
                                  uint16_t *pulse_us,
                                  bool *limited)
{
    int32_t angle = angle_cdeg;
    int32_t pulse;

    if (!ServoActuator_IsConfigValid(config) || (pulse_us == NULL))
    {
        return false;
    }
    if (limited != NULL)
    {
        *limited = false;
    }
    if (angle < config->angle_min_cdeg)
    {
        angle = config->angle_min_cdeg;
        if (limited != NULL) { *limited = true; }
    }
    else if (angle > config->angle_max_cdeg)
    {
        angle = config->angle_max_cdeg;
        if (limited != NULL) { *limited = true; }
    }
    if (angle <= config->angle_center_cdeg)
    {
        pulse = Interpolate(angle,
                            config->angle_min_cdeg,
                            config->angle_center_cdeg,
                            config->pulse_min_us,
                            config->pulse_center_us);
    }
    else
    {
        pulse = Interpolate(angle,
                            config->angle_center_cdeg,
                            config->angle_max_cdeg,
                            config->pulse_center_us,
                            config->pulse_max_us);
    }
    if ((pulse < 0) || (pulse > UINT16_MAX))
    {
        return false;
    }
    *pulse_us = (uint16_t)pulse;
    return true;
}

bool ServoActuator_MapPulseToAngle(const ServoActuatorConfig_t *config,
                                  uint16_t pulse_us,
                                  int16_t *angle_cdeg)
{
    bool low_segment;
    int32_t angle;

    if (!ServoActuator_IsConfigValid(config) || (angle_cdeg == NULL))
    {
        return false;
    }
    low_segment = (config->pulse_min_us < config->pulse_max_us)
                      ? (pulse_us <= config->pulse_center_us)
                      : (pulse_us >= config->pulse_center_us);
    if (low_segment)
    {
        angle = Interpolate(pulse_us,
                            config->pulse_min_us,
                            config->pulse_center_us,
                            config->angle_min_cdeg,
                            config->angle_center_cdeg);
    }
    else
    {
        angle = Interpolate(pulse_us,
                            config->pulse_center_us,
                            config->pulse_max_us,
                            config->angle_center_cdeg,
                            config->angle_max_cdeg);
    }
    if ((angle < INT16_MIN) || (angle > INT16_MAX))
    {
        return false;
    }
    *angle_cdeg = (int16_t)angle;
    return true;
}

bool ServoActuator_Init(ServoActuator_t *servo,
                        const ServoActuatorConfig_t *config,
                        uint32_t now_ms)
{
    if ((servo == NULL) || !ServoActuator_IsConfigValid(config))
    {
        return false;
    }
    servo->config = *config;
    servo->current_pulse_us = config->pulse_center_us;
    servo->target_pulse_us = config->pulse_center_us;
    servo->last_update_ms = now_ms;
    servo->state = SERVO_STATE_DISABLED;
    servo->initialized = true;
    return true;
}

bool ServoActuator_SetTargetAngle(ServoActuator_t *servo,
                                  int16_t angle_cdeg,
                                  bool *limited)
{
    return (servo != NULL) && servo->initialized &&
           ServoActuator_MapAngleToPulse(
               &servo->config, angle_cdeg, &servo->target_pulse_us, limited);
}

bool ServoActuator_SetTargetPulse(ServoActuator_t *servo,
                                  uint16_t pulse_us,
                                  bool *limited)
{
    uint16_t low;
    uint16_t high;

    if ((servo == NULL) || !servo->initialized)
    {
        return false;
    }
    low = (servo->config.pulse_min_us < servo->config.pulse_max_us)
              ? servo->config.pulse_min_us
              : servo->config.pulse_max_us;
    high = (servo->config.pulse_min_us > servo->config.pulse_max_us)
               ? servo->config.pulse_min_us
               : servo->config.pulse_max_us;
    if (limited != NULL) { *limited = false; }
    if (pulse_us < low)
    {
        pulse_us = low;
        if (limited != NULL) { *limited = true; }
    }
    else if (pulse_us > high)
    {
        pulse_us = high;
        if (limited != NULL) { *limited = true; }
    }
    servo->target_pulse_us = pulse_us;
    return true;
}

uint16_t ServoActuator_Update(ServoActuator_t *servo, uint32_t now_ms)
{
    uint32_t dt_ms;
    uint32_t max_step;

    if ((servo == NULL) || !servo->initialized)
    {
        return 0U;
    }
    dt_ms = now_ms - servo->last_update_ms;
    servo->last_update_ms = now_ms;
    if (dt_ms > SERVO_MAX_UPDATE_DT_MS) { dt_ms = SERVO_MAX_UPDATE_DT_MS; }
    max_step = ((uint32_t)servo->config.max_slew_us_per_s * dt_ms) / 1000U;
    if ((dt_ms != 0U) && (max_step == 0U)) { max_step = 1U; }
    if (servo->current_pulse_us < servo->target_pulse_us)
    {
        uint32_t next = (uint32_t)servo->current_pulse_us + max_step;
        servo->current_pulse_us = (next < servo->target_pulse_us)
                                      ? (uint16_t)next
                                      : servo->target_pulse_us;
    }
    else if (servo->current_pulse_us > servo->target_pulse_us)
    {
        uint32_t delta = servo->current_pulse_us - servo->target_pulse_us;
        servo->current_pulse_us = (max_step < delta)
                                      ? (uint16_t)(servo->current_pulse_us - max_step)
                                      : servo->target_pulse_us;
    }
    servo->state = (servo->current_pulse_us == servo->target_pulse_us)
                       ? SERVO_STATE_HOLDING
                       : SERVO_STATE_MOVING;
    return servo->current_pulse_us;
}
