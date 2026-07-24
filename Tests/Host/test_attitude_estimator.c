#include <stdint.h>

#include "attitude_estimator.h"
#include "test_support.h"

void TestAttitudeEstimator_Run(TestContext_t *context)
{
    AttitudeEstimator_t estimator;
    AttitudeOutput_t output = {0};
    Mpu6050ScaledSample_t horizontal = {0, 0, 1000, 0, 0, 0};
    Mpu6050ScaledSample_t roll_45 = {0, 707, 707, 0, 0, 0};
    Mpu6050ScaledSample_t pitch_45 = {-707, 0, 707, 0, 0, 0};
    Mpu6050ScaledSample_t rotating = {0, 0, 1000, 100000, 0, 0};

    TEST_EXPECT(context, !AttitudeEstimator_Init(NULL));
    TEST_EXPECT(context, AttitudeEstimator_Init(&estimator));
    TEST_EXPECT(context, !AttitudeEstimator_Reset(NULL, &horizontal, 0U));
    TEST_EXPECT(context, !AttitudeEstimator_Reset(&estimator, NULL, 0U));
    TEST_EXPECT(context, AttitudeEstimator_Reset(&estimator, &horizontal, 100U));
    TEST_EXPECT(context,
                AttitudeEstimator_Update(&estimator, &horizontal, 110U, &output));
    TEST_EXPECT(context, output.valid);
    TEST_EXPECT(context, output.roll_cdeg == 0);
    TEST_EXPECT(context, output.pitch_cdeg == 0);
    TEST_EXPECT(context, AttitudeEstimator_Reset(&estimator, &roll_45, 200U));
    TEST_EXPECT(context,
                AttitudeEstimator_Update(&estimator, &roll_45, 210U, &output));
    TEST_EXPECT(context, (output.roll_cdeg >= 4490) && (output.roll_cdeg <= 4510));
    TEST_EXPECT(context, AttitudeEstimator_Reset(&estimator, &pitch_45, 300U));
    TEST_EXPECT(context,
                AttitudeEstimator_Update(&estimator, &pitch_45, 310U, &output));
    TEST_EXPECT(context, (output.pitch_cdeg >= 4490) && (output.pitch_cdeg <= 4510));
    TEST_EXPECT(context, AttitudeEstimator_Reset(&estimator, &horizontal, 1000U));
    TEST_EXPECT(context,
                AttitudeEstimator_Update(&estimator, &rotating, 1010U, &output));
    TEST_EXPECT(context, (output.roll_cdeg >= 97) && (output.roll_cdeg <= 99));
    TEST_EXPECT(context,
                AttitudeEstimator_Update(&estimator, &rotating, 1020U, &output));
    TEST_EXPECT(context, output.roll_cdeg > 190);
    TEST_EXPECT(context,
                !AttitudeEstimator_Update(&estimator, &rotating, 1020U, &output));
    TEST_EXPECT(context, !output.valid);
    TEST_EXPECT(context,
                !AttitudeEstimator_Update(&estimator, &rotating, 2000U, &output));
    TEST_EXPECT(context,
                AttitudeEstimator_Update(&estimator, &horizontal, 2010U, &output));
    TEST_EXPECT(context,
                AttitudeEstimator_Reset(&estimator, &horizontal, UINT32_MAX - 4U));
    TEST_EXPECT(context,
                AttitudeEstimator_Update(&estimator, &horizontal, 5U, &output));
    TEST_EXPECT(context, output.valid);
    TEST_EXPECT(context,
                !AttitudeEstimator_Update(&estimator, &horizontal, 6U, NULL));
}
