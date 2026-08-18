#include <stdint.h>

#include <stddef.h>

#include "software_timer.h"
#include "test_support.h"

void TestSoftwareTimer_Run(TestContext_t *context)
{
    SoftwareTimer_t timer = {0U, 0U, false};
    SoftwareTimer_t uninitialized = {17U, 25U, false};

    TEST_EXPECT(context, !SoftwareTimer_Init(NULL, 0U, 100U));
    TEST_EXPECT(context, !SoftwareTimer_Init(&timer, 0U, 0U));
    TEST_EXPECT(context, !SoftwareTimer_IsDue(NULL, 100U));
    TEST_EXPECT(context, !SoftwareTimer_IsDue(&uninitialized, 100U));

    TEST_EXPECT(context, SoftwareTimer_Init(&timer, 0U, 100U));
    TEST_EXPECT(context, !SoftwareTimer_IsDue(&timer, 99U));
    TEST_EXPECT(context, timer.last_run_ms == 0U);
    TEST_EXPECT(context, SoftwareTimer_IsDue(&timer, 100U));
    TEST_EXPECT(context, timer.last_run_ms == 100U);

    TEST_EXPECT(context, SoftwareTimer_IsDue(&timer, 350U));
    TEST_EXPECT(context, timer.last_run_ms == 300U);
    TEST_EXPECT(context, !SoftwareTimer_IsDue(&timer, 399U));
    TEST_EXPECT(context, SoftwareTimer_IsDue(&timer, 600U));
    TEST_EXPECT(context, timer.last_run_ms == 600U);
    TEST_EXPECT(context, SoftwareTimer_IsDue(&timer, 700U));
    TEST_EXPECT(context, timer.last_run_ms == 700U);

    TEST_EXPECT(context, SoftwareTimer_Init(&timer, UINT32_MAX - 49U, 100U));
    TEST_EXPECT(context, !SoftwareTimer_IsDue(&timer, 25U));
    TEST_EXPECT(context, SoftwareTimer_IsDue(&timer, 50U));
    TEST_EXPECT(context, timer.last_run_ms == 50U);

    SoftwareTimer_Reset(&timer, 500U);
    TEST_EXPECT(context, timer.last_run_ms == 500U);
    SoftwareTimer_Reset(NULL, 0U);
    SoftwareTimer_Reset(&uninitialized, 99U);
    TEST_EXPECT(context, uninitialized.last_run_ms == 17U);
}
