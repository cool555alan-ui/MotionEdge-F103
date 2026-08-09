#include "control_service.h"

#include "bsp_pwm.h"
#include "test_support.h"
#include "tim.h"

static void ResetControlHardware(void)
{
    htim3.Instance = TIM3;
    htim3.Init.Prescaler = 71U;
    htim3.Init.Period = 19999U;
    htim3.compare = 0U;
    g_test_pclk1_hz = 36000000U;
    g_test_rcc.CFGR = RCC_CFGR_PPRE1;
    g_test_pwm_start_result = HAL_OK;
    g_test_pwm_stop_result = HAL_OK;
    g_test_pwm_start_count = 0U;
    g_test_pwm_stop_count = 0U;
}

static MotionFrame_t Frame(uint32_t timestamp,
                           uint32_t sequence,
                           int32_t roll_cdeg,
                           int32_t pitch_cdeg)
{
    MotionFrame_t frame = {0};
    frame.timestamp_ms = timestamp;
    frame.sequence = sequence;
    frame.attitude.roll_cdeg = roll_cdeg;
    frame.attitude.pitch_cdeg = pitch_cdeg;
    frame.attitude.valid = true;
    frame.valid = true;
    frame.calibrated = true;
    return frame;
}

void TestControlService_Run(TestContext_t *context)
{
    MotionFrame_t frame = Frame(100U, 1U, 300, -100);
    ControlStatus_t status;
    ControlConfig_t config;
    uint32_t index;

    ResetControlHardware();
    TEST_EXPECT(context, ActuatorService_Init(100U));
    TEST_EXPECT(context, ControlService_Init(100U));
    TEST_EXPECT(context, ControlService_GetStatus(100U, &status) &&
                         !status.enabled && status.mode == CONTROL_MODE_DISABLED);
    TEST_EXPECT(context, ControlService_Enable(ACTUATOR_OWNER_SERIAL,
                                               CONTROL_AXIS_ROLL, &frame, 100U,
                                               true, true) == CONTROL_RESULT_NOT_READY);
    TEST_EXPECT(context, ActuatorService_Arm(ACTUATOR_OWNER_SERIAL) == ACTUATOR_RESULT_OK);
    TEST_EXPECT(context, ControlService_Enable(ACTUATOR_OWNER_SERIAL,
                                               CONTROL_AXIS_ROLL, &frame, 100U,
                                               true, true) == CONTROL_RESULT_OK);
    TEST_EXPECT(context, ControlService_GetStatus(100U, &status) &&
                         status.enabled && status.zero_angle_cdeg == 300);
    TEST_EXPECT(context, ControlService_SetDirection(CONTROL_DIRECTION_REVERSE) ==
                         CONTROL_RESULT_BUSY);
    for (index = 2U; index <= 6U; ++index)
    {
        frame = Frame(90U + index * 10U, index, 300, -100);
        ControlService_Update(&frame, frame.timestamp_ms, true, true, false);
    }
    frame = Frame(160U, 7U, 500, -100);
    ControlService_Update(&frame, 160U, true, true, false);
    TEST_EXPECT(context, ControlService_GetStatus(160U, &status) &&
                         status.active && status.relative_angle_cdeg == 200 &&
                         status.requested_pulse_us == 1502U);
    TEST_EXPECT(context, ControlService_Disable(ACTUATOR_OWNER_MQTT) == CONTROL_RESULT_BUSY);
    TEST_EXPECT(context, ControlService_Disable(ACTUATOR_OWNER_SERIAL) == CONTROL_RESULT_OK);
    TEST_EXPECT(context, ControlService_SetAxis(CONTROL_AXIS_PITCH) == CONTROL_RESULT_OK);
    TEST_EXPECT(context, ControlService_SetDirection(CONTROL_DIRECTION_REVERSE) == CONTROL_RESULT_OK);
    TEST_EXPECT(context, ControlService_SetDeadband(50U) == CONTROL_RESULT_OK);
    TEST_EXPECT(context, ControlService_SetDeadband(10U) ==
                         CONTROL_RESULT_INVALID_ARGUMENT);
    TEST_EXPECT(context, ControlService_GetConfig(&config));
    config.pid.output_min = -50.0F;
    config.pid.output_max = 50.0F;
    config.pid.kp = 2.0F;
    TEST_EXPECT(context, ControlService_SetPidConfig(&config.pid) == CONTROL_RESULT_OK);
    config.pid.kp = 50.01F;
    TEST_EXPECT(context, ControlService_SetPidConfig(&config.pid) ==
                         CONTROL_RESULT_INVALID_ARGUMENT);
    config.pid.kp = 2.0F;
    config.pid.ki = 20.01F;
    TEST_EXPECT(context, ControlService_SetPidConfig(&config.pid) ==
                         CONTROL_RESULT_INVALID_ARGUMENT);
    config.pid.ki = 0.0F;
    config.pid.kd = 20.01F;
    TEST_EXPECT(context, ControlService_SetPidConfig(&config.pid) ==
                         CONTROL_RESULT_INVALID_ARGUMENT);
    config.pid.kd = 0.0F;

    TEST_EXPECT(context, ActuatorService_Arm(ACTUATOR_OWNER_SERIAL) == ACTUATOR_RESULT_OK);
    frame = Frame(200U, 20U, 0, 400);
    TEST_EXPECT(context, ControlService_Enable(ACTUATOR_OWNER_SERIAL,
                                               CONTROL_AXIS_PITCH, &frame, 200U,
                                               true, true) == CONTROL_RESULT_OK);
    /* 真实掉线会同步使应用DEGRADED，仍应报告更具体的Sensor offline。 */
    ControlService_Update(NULL, 210U, false, false, false);
    TEST_EXPECT(context, ControlService_GetStatus(210U, &status) &&
                         !status.enabled &&
                         status.last_fault == CONTROL_FAULT_SENSOR_OFFLINE &&
                         status.fault_count == 1U);

    TEST_EXPECT(context, ActuatorService_Arm(ACTUATOR_OWNER_SERIAL) == ACTUATOR_RESULT_OK);
    frame = Frame(300U, 30U, 0, 400);
    TEST_EXPECT(context, ControlService_Enable(ACTUATOR_OWNER_SERIAL,
                                               CONTROL_AXIS_PITCH, &frame, 300U,
                                               true, true) == CONTROL_RESULT_OK);
    ControlService_Update(&frame, 301U, false, true, true);
    TEST_EXPECT(context, ControlService_GetStatus(301U, &status) &&
                         status.last_fault == CONTROL_FAULT_APP_FAULT &&
                         status.fault_count == 2U);
}
