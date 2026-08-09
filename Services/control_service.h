#ifndef CONTROL_SERVICE_H
#define CONTROL_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

#include "actuator_service.h"
#include "motion_service.h"
#include "pid_controller.h"

#define CONTROL_MOTION_TIMEOUT_MS 100U
#define CONTROL_WARMUP_SAMPLE_COUNT 5U
#define CONTROL_STATUS_PAYLOAD_SIZE 94U

typedef enum
{
    CONTROL_MODE_DISABLED = 0,
    CONTROL_MODE_PID_ATTITUDE
} ControlMode_t;

typedef enum
{
    CONTROL_AXIS_ROLL = 0,
    CONTROL_AXIS_PITCH
} ControlAxis_t;

typedef enum
{
    CONTROL_DIRECTION_NORMAL = 0,
    CONTROL_DIRECTION_REVERSE
} ControlDirection_t;

typedef enum
{
    CONTROL_FAULT_NONE = 0,
    CONTROL_FAULT_STALE_MOTION,
    CONTROL_FAULT_SENSOR_OFFLINE,
    CONTROL_FAULT_NOT_CALIBRATED,
    CONTROL_FAULT_APP_FAULT,
    CONTROL_FAULT_ACTUATOR,
    CONTROL_FAULT_NONFINITE,
    CONTROL_FAULT_INVALID_DT
} ControlFault_t;

typedef enum
{
    CONTROL_RESULT_OK = 0,
    CONTROL_RESULT_INVALID_ARGUMENT,
    CONTROL_RESULT_NOT_READY,
    CONTROL_RESULT_BUSY,
    CONTROL_RESULT_ACTUATOR_ERROR
} ControlResult_t;

typedef struct
{
    PidControllerConfig_t pid;
    ControlAxis_t axis;
    ControlDirection_t direction;
    uint16_t deadband_cdeg;
} ControlConfig_t;

typedef struct
{
    ControlMode_t mode;
    ControlAxis_t axis;
    ControlDirection_t direction;
    PidIntegralMode_t integral_mode;
    bool enabled;
    bool active;
    bool saturated;
    bool in_deadband;
    ControlFault_t last_fault;
    int32_t zero_angle_cdeg;
    int32_t measured_angle_cdeg;
    int32_t relative_angle_cdeg;
    int32_t effective_error_cdeg;
    uint16_t deadband_cdeg;
    int32_t kp_milli;
    int32_t ki_milli;
    int32_t kd_milli;
    int32_t p_term_milli;
    int32_t i_term_milli;
    int32_t d_term_milli;
    int16_t output_us;
    uint16_t requested_pulse_us;
    uint16_t actual_pulse_us;
    uint32_t motion_age_ms;
    uint32_t update_count;
    uint32_t invalid_dt_count;
    uint32_t nonfinite_input_count;
    uint32_t stale_motion_count;
    uint32_t integrator_saturation_count;
    uint32_t target_limit_count;
    uint32_t fault_count;
    uint32_t deadband_entry_count;
    uint32_t deadband_exit_count;
} ControlStatus_t;

bool ControlService_Init(uint32_t now_ms);
ControlResult_t ControlService_Enable(ActuatorOwner_t owner,
                                      ControlAxis_t axis,
                                      const MotionFrame_t *motion,
                                      uint32_t now_ms,
                                      bool app_running,
                                      bool sensor_online);
ControlResult_t ControlService_Disable(ActuatorOwner_t owner);
ControlResult_t ControlService_SetZero(ActuatorOwner_t owner,
                                       const MotionFrame_t *motion,
                                       uint32_t now_ms);
ControlResult_t ControlService_SetAxis(ControlAxis_t axis);
ControlResult_t ControlService_SetDirection(ControlDirection_t direction);
ControlResult_t ControlService_SetPidConfig(const PidControllerConfig_t *config);
ControlResult_t ControlService_SetDeadband(uint16_t deadband_cdeg);
void ControlService_NotifyEmergencyStop(void);
void ControlService_Update(const MotionFrame_t *motion,
                           uint32_t now_ms,
                           bool app_running,
                           bool sensor_online,
                           bool app_fault);
bool ControlService_GetConfig(ControlConfig_t *config);
bool ControlService_GetStatus(uint32_t now_ms, ControlStatus_t *status);

#endif /* CONTROL_SERVICE_H */
