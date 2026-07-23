#include <string.h>

#include "app_status.h"
#include "test_support.h"

void TestAppStatus_Run(TestContext_t *context)
{
    AppStatus_Init();
    TEST_EXPECT(context, AppStatus_GetState() == APP_STATE_BOOT);
    TEST_EXPECT(context, strcmp(AppStatus_ToString(APP_STATE_BOOT), "BOOT") == 0);

    TEST_EXPECT(context, AppStatus_SetState(APP_STATE_INITIALIZING));
    TEST_EXPECT(context, AppStatus_GetState() == APP_STATE_INITIALIZING);
    TEST_EXPECT(context,
                strcmp(AppStatus_ToString(APP_STATE_INITIALIZING), "INITIALIZING") == 0);

    TEST_EXPECT(context, AppStatus_SetState(APP_STATE_RUNNING));
    TEST_EXPECT(context, AppStatus_GetState() == APP_STATE_RUNNING);
    TEST_EXPECT(context, strcmp(AppStatus_ToString(APP_STATE_RUNNING), "RUNNING") == 0);

    TEST_EXPECT(context, AppStatus_SetState(APP_STATE_DEGRADED));
    TEST_EXPECT(context, AppStatus_GetState() == APP_STATE_DEGRADED);
    TEST_EXPECT(context, strcmp(AppStatus_ToString(APP_STATE_DEGRADED), "DEGRADED") == 0);

    TEST_EXPECT(context, AppStatus_SetState(APP_STATE_FAULT));
    TEST_EXPECT(context, AppStatus_GetState() == APP_STATE_FAULT);
    TEST_EXPECT(context, strcmp(AppStatus_ToString(APP_STATE_FAULT), "FAULT") == 0);

    TEST_EXPECT(context, !AppStatus_SetState((AppState_t)99));
    TEST_EXPECT(context, strcmp(AppStatus_ToString((AppState_t)99), "UNKNOWN") == 0);
}
