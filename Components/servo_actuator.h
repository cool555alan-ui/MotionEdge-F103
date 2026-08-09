#ifndef SERVO_ACTUATOR_H
#define SERVO_ACTUATOR_H

#include <stdbool.h>
#include <stdint.h>

typedef struct
{
    uint16_t pulse_min_us;
    uint16_t pulse_center_us;
    uint16_t pulse_max_us;
    int16_t angle_min_cdeg;
    int16_t angle_center_cdeg;
    int16_t angle_max_cdeg;
    uint16_t max_slew_us_per_s;
} ServoActuatorConfig_t;

typedef enum
{
    SERVO_STATE_DISABLED = 0,
    SERVO_STATE_ARMING,
    SERVO_STATE_READY,
    SERVO_STATE_MOVING,
    SERVO_STATE_HOLDING,
    SERVO_STATE_FAULT
} ServoActuatorState_t;

typedef struct
{
    ServoActuatorConfig_t config;
    uint16_t current_pulse_us;
    uint16_t target_pulse_us;
    uint32_t last_update_ms;
    ServoActuatorState_t state;
    bool initialized;
} ServoActuator_t;

bool ServoActuator_IsConfigValid(const ServoActuatorConfig_t *config);
bool ServoActuator_MapAngleToPulse(const ServoActuatorConfig_t *config,
                                  int16_t angle_cdeg,
                                  uint16_t *pulse_us,
                                  bool *limited);
bool ServoActuator_MapPulseToAngle(const ServoActuatorConfig_t *config,
                                  uint16_t pulse_us,
                                  int16_t *angle_cdeg);
bool ServoActuator_Init(ServoActuator_t *servo,
                        const ServoActuatorConfig_t *config,
                        uint32_t now_ms);
bool ServoActuator_SetTargetAngle(ServoActuator_t *servo,
                                  int16_t angle_cdeg,
                                  bool *limited);
bool ServoActuator_SetTargetPulse(ServoActuator_t *servo,
                                  uint16_t pulse_us,
                                  bool *limited);
uint16_t ServoActuator_Update(ServoActuator_t *servo, uint32_t now_ms);

#endif /* SERVO_ACTUATOR_H */
