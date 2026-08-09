#include "pid_controller.h"

#include <math.h>

#include "test_support.h"

static bool Near(float actual, float expected, float tolerance)
{
    return fabsf(actual - expected) <= tolerance;
}

static PidControllerConfig_t DefaultConfig(void)
{
    const PidControllerConfig_t config = {
        2.0F, 0.0F, 0.0F, -10.0F, 10.0F, -5.0F, 5.0F,
        0.5F, 0.005F, 0.030F, PID_INTEGRAL_MODE_DISABLED, 0.9F};
    return config;
}

void TestPidController_Run(TestContext_t *context)
{
    PidController_t pid;
    PidControllerConfig_t config = DefaultConfig();
    PidControllerOutput_t output;

    TEST_EXPECT(context, PidController_IsConfigValid(&config));
    TEST_EXPECT(context, PidController_Init(&pid, &config));
    TEST_EXPECT(context, PidController_Reset(&pid, 0.0F));
    TEST_EXPECT(context, PidController_Update(&pid, 2.0F, 2.0F, 0.01F, &output));
    TEST_EXPECT(context, Near(output.p_term, 4.0F, 0.001F) &&
                         Near(output.output, 4.0F, 0.001F));
    TEST_EXPECT(context, PidController_Update(&pid, -2.0F, -2.0F, 0.01F, &output));
    TEST_EXPECT(context, Near(output.output, -4.0F, 0.001F));
    TEST_EXPECT(context, PidController_Update(&pid, 20.0F, 20.0F, 0.01F, &output));
    TEST_EXPECT(context, output.saturated && Near(output.output, 10.0F, 0.001F));
    TEST_EXPECT(context, !PidController_Update(&pid, 1.0F, 1.0F, 0.001F, &output));
    TEST_EXPECT(context, !PidController_Update(&pid, NAN, 1.0F, 0.01F, &output));

    config.kp = 0.0F;
    config.ki = 10.0F;
    config.integral_mode = PID_INTEGRAL_MODE_BOUNDED;
    TEST_EXPECT(context, PidController_Init(&pid, &config));
    TEST_EXPECT(context, PidController_Reset(&pid, 0.0F));
    TEST_EXPECT(context, PidController_Update(&pid, 1.0F, 0.0F, 0.01F, &output));
    TEST_EXPECT(context, Near(output.i_term, 0.1F, 0.001F));
    for (int index = 0; index < 100; ++index)
    {
        TEST_EXPECT(context, PidController_Update(&pid, 100.0F, 0.0F, 0.01F, &output));
    }
    TEST_EXPECT(context, output.integrator_limited || output.i_term <= 5.0F);

    config.integral_mode = PID_INTEGRAL_MODE_LEAKY;
    config.ki = 0.0F;
    TEST_EXPECT(context, PidController_SetConfig(&pid, &config));
    TEST_EXPECT(context, PidController_Update(&pid, 0.0F, 0.0F, 0.01F, &output));
    TEST_EXPECT(context, output.i_term <= 5.0F);

    config = DefaultConfig();
    config.kp = 0.0F;
    config.kd = 1.0F;
    TEST_EXPECT(context, PidController_Init(&pid, &config));
    TEST_EXPECT(context, PidController_Reset(&pid, 0.0F));
    TEST_EXPECT(context, PidController_Update(&pid, 0.0F, 1.0F, 0.01F, &output));
    TEST_EXPECT(context, output.d_term < 0.0F && output.saturated);
    TEST_EXPECT(context, PidController_Reset(&pid, 3.0F));
    TEST_EXPECT(context, PidController_Update(&pid, 0.0F, 3.0F, 0.01F, &output));
    TEST_EXPECT(context, Near(output.d_term, 0.0F, 0.001F));

    config.output_min = 1.0F;
    TEST_EXPECT(context, !PidController_IsConfigValid(&config));
    config = DefaultConfig();
    config.derivative_alpha = 1.1F;
    TEST_EXPECT(context, !PidController_IsConfigValid(&config));
    config = DefaultConfig();
    config.integral_leak_factor = -0.1F;
    TEST_EXPECT(context, !PidController_IsConfigValid(&config));
}
