#include <stdio.h>

#include "test_support.h"

void TestSoftwareTimer_Run(TestContext_t *context);
void TestAppStatus_Run(TestContext_t *context);
void TestLogger_Run(TestContext_t *context);
void TestI2cScanner_Run(TestContext_t *context);
void TestMpu6500_Run(TestContext_t *context);
void TestLowPassFilter_Run(TestContext_t *context);
void TestAttitudeEstimator_Run(TestContext_t *context);
void TestCalibrationService_Run(TestContext_t *context);
void TestMotionService_Run(TestContext_t *context);
void TestCsvTelemetry_Run(TestContext_t *context);
void TestProtocol_Run(TestContext_t *context);

void Test_RecordAssertion(TestContext_t *context,
                          bool condition,
                          const char *expression,
                          const char *file,
                          int line)
{
    if (context == NULL)
    {
        return;
    }

    ++context->assertion_count;
    if (!condition)
    {
        ++context->failure_count;
        (void)fprintf(stderr, "FAIL: %s (%s:%d)\n", expression, file, line);
    }
}

int main(void)
{
    TestContext_t context = {0U, 0U};

    TestSoftwareTimer_Run(&context);
    TestAppStatus_Run(&context);
    TestLogger_Run(&context);
    TestI2cScanner_Run(&context);
    TestMpu6500_Run(&context);
    TestLowPassFilter_Run(&context);
    TestAttitudeEstimator_Run(&context);
    TestCalibrationService_Run(&context);
    TestMotionService_Run(&context);
    TestCsvTelemetry_Run(&context);
    TestProtocol_Run(&context);

    (void)printf("Host assertions: total=%u passed=%u failed=%u\n",
                 context.assertion_count,
                 context.assertion_count - context.failure_count,
                 context.failure_count);

    return (context.failure_count == 0U) ? 0 : 1;
}
