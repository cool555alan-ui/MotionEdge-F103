#include "pid_controller.h"

#include <math.h>
#include <stddef.h>

static float Clamp(float value, float minimum, float maximum)
{
    if (value < minimum) { return minimum; }
    if (value > maximum) { return maximum; }
    return value;
}

bool PidController_IsConfigValid(const PidControllerConfig_t *config)
{
    if ((config == NULL) || !isfinite(config->kp) ||
        !isfinite(config->ki) || !isfinite(config->kd) ||
        !isfinite(config->output_min) || !isfinite(config->output_max) ||
        !isfinite(config->integrator_min) ||
        !isfinite(config->integrator_max) ||
        !isfinite(config->derivative_alpha) ||
        !isfinite(config->dt_min_s) || !isfinite(config->dt_max_s) ||
        !isfinite(config->integral_leak_factor))
    {
        return false;
    }
    return (config->kp >= 0.0F) && (config->ki >= 0.0F) &&
           (config->kd >= 0.0F) &&
           (config->output_min < config->output_max) &&
           (config->output_min <= 0.0F) &&
           (config->output_max >= 0.0F) &&
           (config->integrator_min <= 0.0F) &&
           (config->integrator_max >= 0.0F) &&
           (config->integrator_min <= config->integrator_max) &&
           (config->derivative_alpha >= 0.0F) &&
           (config->derivative_alpha <= 1.0F) &&
           (config->dt_min_s > 0.0F) &&
           (config->dt_min_s <= config->dt_max_s) &&
           (config->integral_mode <= PID_INTEGRAL_MODE_LEAKY) &&
           (config->integral_leak_factor >= 0.0F) &&
           (config->integral_leak_factor <= 1.0F);
}

bool PidController_Init(PidController_t *controller,
                        const PidControllerConfig_t *config)
{
    if ((controller == NULL) || !PidController_IsConfigValid(config))
    {
        return false;
    }
    controller->config = *config;
    controller->state = (PidControllerState_t){0};
    return true;
}

bool PidController_SetConfig(PidController_t *controller,
                             const PidControllerConfig_t *config)
{
    if ((controller == NULL) || !PidController_IsConfigValid(config))
    {
        return false;
    }
    controller->config = *config;
    controller->state.integrator = Clamp(controller->state.integrator,
                                         config->integrator_min,
                                         config->integrator_max);
    return true;
}

bool PidController_Reset(PidController_t *controller, float measurement)
{
    if ((controller == NULL) || !isfinite(measurement)) { return false; }
    controller->state = (PidControllerState_t){0};
    controller->state.previous_measurement = measurement;
    controller->state.initialized = true;
    return true;
}

bool PidController_Update(PidController_t *controller,
                          float error,
                          float measurement,
                          float dt_s,
                          PidControllerOutput_t *result)
{
    float candidate_integrator;
    float derivative_raw;
    float unsaturated;
    bool pushes_high;
    bool pushes_low;

    if ((controller == NULL) || (result == NULL) ||
        !PidController_IsConfigValid(&controller->config) ||
        !isfinite(error) || !isfinite(measurement) || !isfinite(dt_s) ||
        (dt_s < controller->config.dt_min_s) ||
        (dt_s > controller->config.dt_max_s))
    {
        return false;
    }
    if (!controller->state.initialized &&
        !PidController_Reset(controller, measurement))
    {
        return false;
    }

    result->p_term = controller->config.kp * error;
    derivative_raw = -controller->config.kd *
                     (measurement - controller->state.previous_measurement) /
                     dt_s;
    controller->state.derivative_state +=
        controller->config.derivative_alpha *
        (derivative_raw - controller->state.derivative_state);
    result->d_term = controller->state.derivative_state;

    candidate_integrator = controller->state.integrator;
    if (controller->config.integral_mode == PID_INTEGRAL_MODE_DISABLED)
    {
        candidate_integrator = 0.0F;
    }
    else
    {
        if (controller->config.integral_mode == PID_INTEGRAL_MODE_LEAKY)
        {
            candidate_integrator *= controller->config.integral_leak_factor;
        }
        candidate_integrator += controller->config.ki * error * dt_s;
        candidate_integrator = Clamp(candidate_integrator,
                                     controller->config.integrator_min,
                                     controller->config.integrator_max);
    }

    unsaturated = result->p_term + candidate_integrator + result->d_term;
    pushes_high = (unsaturated > controller->config.output_max) && (error > 0.0F);
    pushes_low = (unsaturated < controller->config.output_min) && (error < 0.0F);
    result->integrator_limited = pushes_high || pushes_low;
    if (result->integrator_limited)
    {
        candidate_integrator = controller->state.integrator;
        unsaturated = result->p_term + candidate_integrator + result->d_term;
    }
    controller->state.integrator = candidate_integrator;
    controller->state.previous_error = error;
    controller->state.previous_measurement = measurement;

    result->i_term = candidate_integrator;
    result->output = Clamp(unsaturated,
                           controller->config.output_min,
                           controller->config.output_max);
    result->saturated = result->output != unsaturated;
    if (!isfinite(result->p_term) || !isfinite(result->i_term) ||
        !isfinite(result->d_term) || !isfinite(result->output))
    {
        return false;
    }
    return true;
}
