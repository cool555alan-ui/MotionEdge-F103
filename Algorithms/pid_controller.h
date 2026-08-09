#ifndef PID_CONTROLLER_H
#define PID_CONTROLLER_H

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    PID_INTEGRAL_MODE_DISABLED = 0,
    PID_INTEGRAL_MODE_BOUNDED,
    PID_INTEGRAL_MODE_LEAKY
} PidIntegralMode_t;

typedef struct
{
    float kp;
    float ki;
    float kd;
    float output_min;
    float output_max;
    float integrator_min;
    float integrator_max;
    float derivative_alpha;
    float dt_min_s;
    float dt_max_s;
    PidIntegralMode_t integral_mode;
    float integral_leak_factor;
} PidControllerConfig_t;

typedef struct
{
    float integrator;
    float previous_error;
    float previous_measurement;
    float derivative_state;
    bool initialized;
} PidControllerState_t;

typedef struct
{
    float p_term;
    float i_term;
    float d_term;
    float output;
    bool saturated;
    bool integrator_limited;
} PidControllerOutput_t;

typedef struct
{
    PidControllerConfig_t config;
    PidControllerState_t state;
} PidController_t;

bool PidController_IsConfigValid(const PidControllerConfig_t *config);
bool PidController_Init(PidController_t *controller,
                        const PidControllerConfig_t *config);
bool PidController_SetConfig(PidController_t *controller,
                             const PidControllerConfig_t *config);
bool PidController_Reset(PidController_t *controller, float measurement);
bool PidController_Update(PidController_t *controller,
                          float error,
                          float measurement,
                          float dt_s,
                          PidControllerOutput_t *result);

#endif /* PID_CONTROLLER_H */
