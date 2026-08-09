#include "servo_actuator.h"

#include "test_support.h"

void TestServoActuator_Run(TestContext_t *context)
{
    ServoActuatorConfig_t config = {1000U, 1500U, 2000U,
                                    -4500, 0, 4500, 500U};
    ServoActuatorConfig_t reverse = {2000U, 1500U, 1000U,
                                     -4500, 0, 4500, 500U};
    ServoActuatorConfig_t asymmetric = {1100U, 1475U, 1900U,
                                        -3000, 500, 6000, 600U};
    ServoActuator_t servo;
    uint16_t pulse = 0U;
    int16_t angle = 0;
    bool limited = false;

    TEST_EXPECT(context, ServoActuator_IsConfigValid(&config));
    TEST_EXPECT(context, ServoActuator_MapAngleToPulse(&config, -4500, &pulse, NULL) && pulse == 1000U);
    TEST_EXPECT(context, ServoActuator_MapAngleToPulse(&config, 0, &pulse, NULL) && pulse == 1500U);
    TEST_EXPECT(context, ServoActuator_MapAngleToPulse(&config, 4500, &pulse, NULL) && pulse == 2000U);
    TEST_EXPECT(context, ServoActuator_MapAngleToPulse(&config, 2250, &pulse, NULL) && pulse == 1750U);
    TEST_EXPECT(context, ServoActuator_MapAngleToPulse(&config, -5000, &pulse, &limited) && limited && pulse == 1000U);
    TEST_EXPECT(context, ServoActuator_MapAngleToPulse(&reverse, -4500, &pulse, NULL) && pulse == 2000U);
    TEST_EXPECT(context, ServoActuator_MapAngleToPulse(&reverse, 4500, &pulse, NULL) && pulse == 1000U);
    TEST_EXPECT(context, ServoActuator_MapAngleToPulse(&asymmetric, 500, &pulse, NULL) && pulse == 1475U);
    TEST_EXPECT(context, ServoActuator_MapAngleToPulse(&asymmetric, 3250, &pulse, NULL) && pulse == 1687U);
    config.pulse_center_us = config.pulse_min_us;
    TEST_EXPECT(context, !ServoActuator_IsConfigValid(&config));
    config = (ServoActuatorConfig_t){1000U, 1500U, 2000U, -4500, 0, 4500, 500U};
    TEST_EXPECT(context, ServoActuator_Init(&servo, &config, UINT32_MAX - 5U));
    TEST_EXPECT(context, ServoActuator_SetTargetPulse(&servo, 2000U, NULL));
    TEST_EXPECT(context, ServoActuator_Update(&servo, 4U) == 1505U);
    TEST_EXPECT(context, ServoActuator_Update(&servo, 54U) == 1530U);
    TEST_EXPECT(context, ServoActuator_Update(&servo, 1000U) == 1580U);
    TEST_EXPECT(context, ServoActuator_SetTargetPulse(&servo, 1000U, NULL));
    TEST_EXPECT(context, ServoActuator_Update(&servo, 1010U) == 1575U);
    TEST_EXPECT(context, ServoActuator_MapPulseToAngle(&config, 1575U, &angle) && angle == 675);
}
