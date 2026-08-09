#ifndef ACTUATOR_SERVICE_H
#define ACTUATOR_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

#include "servo_actuator.h"

#define ACTUATOR_COMMAND_TIMEOUT_MS 1000U
#define ACTUATOR_STATUS_PAYLOAD_SIZE 36U

typedef enum
{
    ACTUATOR_MODE_DISABLED = 0,
    ACTUATOR_MODE_MANUAL,
    ACTUATOR_MODE_ATTITUDE_HOLD
} ActuatorMode_t;

typedef enum
{
    ACTUATOR_OWNER_NONE = 0,
    ACTUATOR_OWNER_LOCAL,
    ACTUATOR_OWNER_SERIAL,
    ACTUATOR_OWNER_MQTT,
    ACTUATOR_OWNER_CONTROL_LOOP
} ActuatorOwner_t;

typedef enum
{
    ACTUATOR_RESULT_OK = 0,
    ACTUATOR_RESULT_INVALID_ARGUMENT,
    ACTUATOR_RESULT_NOT_ARMED,
    ACTUATOR_RESULT_OWNER_CONFLICT,
    ACTUATOR_RESULT_FAULT,
    ACTUATOR_RESULT_UNSUPPORTED,
    ACTUATOR_RESULT_HARDWARE
} ActuatorResult_t;

typedef struct
{
    ActuatorMode_t mode;
    ServoActuatorState_t state;
    bool armed;
    ActuatorOwner_t owner;
    int16_t target_angle_cdeg;
    int16_t current_angle_cdeg;
    uint16_t target_pulse_us;
    uint16_t current_pulse_us;
    uint16_t safe_min_us;
    uint16_t safe_max_us;
    uint32_t command_age_ms;
    uint32_t timeout_count;
    uint32_t limit_count;
    uint32_t fault_count;
    uint32_t estop_count;
} ActuatorStatus_t;

bool ActuatorService_Init(uint32_t now_ms);
ActuatorResult_t ActuatorService_Arm(ActuatorOwner_t owner);
ActuatorResult_t ActuatorService_Disarm(ActuatorOwner_t owner);
ActuatorResult_t ActuatorService_SetTargetAngle(ActuatorOwner_t owner,
                                                int16_t angle_cdeg);
ActuatorResult_t ActuatorService_SetRawPulse(ActuatorOwner_t owner,
                                             uint16_t pulse_us);
ActuatorResult_t ActuatorService_Center(ActuatorOwner_t owner);
ActuatorResult_t ActuatorService_EmergencyStop(ActuatorOwner_t owner);
void ActuatorService_Update(uint32_t now_ms,
                            bool app_fault,
                            bool motion_online,
                            bool motion_stale);
bool ActuatorService_GetStatus(uint32_t now_ms, ActuatorStatus_t *status);
bool ActuatorService_GetCurrentStatus(ActuatorStatus_t *status);

#endif /* ACTUATOR_SERVICE_H */
