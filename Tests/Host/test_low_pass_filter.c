#include <math.h>
#include <stddef.h>

#include "low_pass_filter.h"
#include "test_support.h"

void TestLowPassFilter_Run(TestContext_t *context)
{
    LowPassFilter_t filter = {0};
    float output = 0.0F;

    TEST_EXPECT(context, !LowPassFilter_Init(NULL, 0.5F));
    TEST_EXPECT(context, !LowPassFilter_Init(&filter, 0.0F));
    TEST_EXPECT(context, !LowPassFilter_Init(&filter, -0.1F));
    TEST_EXPECT(context, !LowPassFilter_Init(&filter, 1.1F));
    TEST_EXPECT(context, !LowPassFilter_Init(&filter, NAN));
    TEST_EXPECT(context, !LowPassFilter_Init(&filter, INFINITY));
    TEST_EXPECT(context, LowPassFilter_Init(&filter, 0.2F));
    TEST_EXPECT(context, !filter.initialized);
    TEST_EXPECT(context, !LowPassFilter_Update(NULL, 1.0F, &output));
    TEST_EXPECT(context, !LowPassFilter_Update(&filter, 1.0F, NULL));
    TEST_EXPECT(context, !LowPassFilter_Update(&filter, NAN, &output));
    TEST_EXPECT(context, !LowPassFilter_Update(&filter, INFINITY, &output));
    TEST_EXPECT(context, LowPassFilter_Update(&filter, 10.0F, &output));
    TEST_EXPECT(context, fabsf(output - 10.0F) < 0.001F);
    TEST_EXPECT(context, LowPassFilter_Update(&filter, 20.0F, &output));
    TEST_EXPECT(context, fabsf(output - 12.0F) < 0.001F);
    TEST_EXPECT(context, LowPassFilter_Update(&filter, 20.0F, &output));
    TEST_EXPECT(context, fabsf(output - 13.6F) < 0.001F);
    TEST_EXPECT(context, LowPassFilter_Reset(&filter, -5.0F));
    TEST_EXPECT(context, LowPassFilter_Update(&filter, -5.0F, &output));
    TEST_EXPECT(context, fabsf(output + 5.0F) < 0.001F);
    TEST_EXPECT(context, !LowPassFilter_Reset(&filter, NAN));
    TEST_EXPECT(context, LowPassFilter_Init(&filter, 1.0F));
    TEST_EXPECT(context, LowPassFilter_Update(&filter, 3.0F, &output));
    TEST_EXPECT(context, LowPassFilter_Update(&filter, -7.0F, &output));
    TEST_EXPECT(context, fabsf(output + 7.0F) < 0.001F);
}
