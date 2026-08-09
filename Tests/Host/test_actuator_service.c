#include "actuator_service.h"

#include "bsp_pwm.h"
#include "test_support.h"
#include "tim.h"

static void ResetHardware(void)
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

void TestPwm_Run(TestContext_t *context)
{
    ResetHardware();
    TEST_EXPECT(context, BspPwm_Init() == BSP_PWM_OK);
    TEST_EXPECT(context, !BspPwm_IsRunning());
    TEST_EXPECT(context, BspPwm_SetPulseUs(1000U) == BSP_PWM_OK && htim3.compare == 1000U);
    TEST_EXPECT(context, BspPwm_SetPulseUs(2000U) == BSP_PWM_OK && htim3.compare == 2000U);
    TEST_EXPECT(context, BspPwm_SetPulseUs(20000U) == BSP_PWM_ERROR_INVALID_ARG);
    TEST_EXPECT(context, BspPwm_Start() == BSP_PWM_OK && BspPwm_IsRunning());
    TEST_EXPECT(context, g_test_pwm_start_count == 1U);
    TEST_EXPECT(context, BspPwm_Stop() == BSP_PWM_OK && !BspPwm_IsRunning());
    TEST_EXPECT(context, g_test_pwm_stop_count == 1U);
    htim3.Instance = NULL;
    TEST_EXPECT(context, BspPwm_Init() == BSP_PWM_ERROR_NOT_READY);
}

void TestActuatorService_Run(TestContext_t *context)
{
    ActuatorStatus_t status;

    ResetHardware();
    TEST_EXPECT(context, ActuatorService_Init(100U));
    TEST_EXPECT(context, ActuatorService_GetStatus(100U, &status));
    TEST_EXPECT(context, !status.armed && status.mode == ACTUATOR_MODE_DISABLED);
    TEST_EXPECT(context, status.safe_min_us == 1450U &&
                         status.safe_max_us == 1550U);
    TEST_EXPECT(context, ActuatorService_SetTargetAngle(ACTUATOR_OWNER_SERIAL, 1000) == ACTUATOR_RESULT_NOT_ARMED);
    TEST_EXPECT(context, ActuatorService_Arm(ACTUATOR_OWNER_SERIAL) == ACTUATOR_RESULT_OK);
    TEST_EXPECT(context, BspPwm_IsRunning() && htim3.compare == 1500U);
    TEST_EXPECT(context, ActuatorService_Arm(ACTUATOR_OWNER_MQTT) == ACTUATOR_RESULT_OWNER_CONFLICT);
    TEST_EXPECT(context, ActuatorService_SetTargetAngle(ACTUATOR_OWNER_MQTT, 1000) == ACTUATOR_RESULT_OWNER_CONFLICT);
    TEST_EXPECT(context, ActuatorService_SetTargetAngle(ACTUATOR_OWNER_SERIAL, 4500) == ACTUATOR_RESULT_OK);
    TEST_EXPECT(context, ActuatorService_SetRawPulse(ACTUATOR_OWNER_SERIAL, 2000U) == ACTUATOR_RESULT_OK);
    TEST_EXPECT(context, ActuatorService_GetStatus(100U, &status) &&
                         status.target_pulse_us == 1550U &&
                         status.limit_count == 1U);
    ActuatorService_Update(110U, false, true, false);
    TEST_EXPECT(context, ActuatorService_GetStatus(110U, &status) && status.current_pulse_us == 1505U);
    ActuatorService_Update(1110U, false, true, false);
    TEST_EXPECT(context, ActuatorService_GetStatus(1110U, &status) && status.timeout_count == 1U && status.target_pulse_us == 1500U);
    TEST_EXPECT(context, ActuatorService_Center(ACTUATOR_OWNER_SERIAL) == ACTUATOR_RESULT_OK);
    TEST_EXPECT(context, ActuatorService_Disarm(ACTUATOR_OWNER_MQTT) == ACTUATOR_RESULT_OK);
    TEST_EXPECT(context, !BspPwm_IsRunning());
    TEST_EXPECT(context, ActuatorService_Arm(ACTUATOR_OWNER_SERIAL) == ACTUATOR_RESULT_OK);
    TEST_EXPECT(context, ActuatorService_EmergencyStop(ACTUATOR_OWNER_MQTT) == ACTUATOR_RESULT_OK);
    TEST_EXPECT(context, ActuatorService_GetStatus(1200U, &status) && !status.armed && status.estop_count == 1U);
    TEST_EXPECT(context, ActuatorService_Arm(ACTUATOR_OWNER_SERIAL) == ACTUATOR_RESULT_OK);
    ActuatorService_Update(1210U, true, true, false);
    TEST_EXPECT(context, ActuatorService_GetStatus(1210U, &status) && status.state == SERVO_STATE_FAULT && !BspPwm_IsRunning());
}
