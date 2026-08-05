#include <stdint.h>
#include <string.h>

#include "app_config.h"
#include "logger.h"
#include "test_support.h"

static uint8_t s_capture_buffer[APP_LOG_BUFFER_SIZE * 2U];
static size_t s_capture_length = 0U;
static unsigned int s_lock_count = 0U;
static unsigned int s_unlock_count = 0U;
static bool s_lock_success = true;

static bool MockLock(void)
{
    ++s_lock_count;
    return s_lock_success;
}

static void MockUnlock(void)
{
    ++s_unlock_count;
}

static void ResetCapture(void)
{
    (void)memset(s_capture_buffer, 0, sizeof(s_capture_buffer));
    s_capture_length = 0U;
}

static bool CaptureWriter(const uint8_t *data, size_t length)
{
    if ((data == NULL) || (length > sizeof(s_capture_buffer)))
    {
        return false;
    }

    (void)memcpy(s_capture_buffer, data, length);
    s_capture_length = length;
    return true;
}

void TestLogger_Run(TestContext_t *context)
{
    char long_message[APP_LOG_BUFFER_SIZE * 2U];
    const char expected_info[] = "[INFO][APP] ready\r\n";
    const char expected_general[] = "[ERROR][GENERAL] failed\r\n";
    const char expected_formatted[] = "[INFO][TEST] value=42\r\n";

    ResetCapture();
    TEST_EXPECT(context, !Logger_Write(LOG_LEVEL_INFO, "APP", "not initialized"));
    TEST_EXPECT(context, !Logger_Init(NULL, LOG_LEVEL_INFO));
    TEST_EXPECT(context, Logger_Init(CaptureWriter, LOG_LEVEL_INFO));
    TEST_EXPECT(context, !Logger_SetLock(MockLock, NULL));
    TEST_EXPECT(context, Logger_SetLock(MockLock, MockUnlock));

    TEST_EXPECT(context, Logger_Write(LOG_LEVEL_INFO, "APP", "ready"));
    TEST_EXPECT(context, s_capture_length == (sizeof(expected_info) - 1U));
    TEST_EXPECT(context,
                memcmp(s_capture_buffer, expected_info, sizeof(expected_info) - 1U) == 0);
    TEST_EXPECT(context, s_capture_buffer[s_capture_length - 2U] == '\r');
    TEST_EXPECT(context, s_capture_buffer[s_capture_length - 1U] == '\n');
    TEST_EXPECT(context, s_lock_count == 1U);
    TEST_EXPECT(context, s_unlock_count == 1U);

    ResetCapture();
    TEST_EXPECT(context, Logger_SetLevel(LOG_LEVEL_WARN));
    TEST_EXPECT(context, Logger_Write(LOG_LEVEL_INFO, "APP", "filtered"));
    TEST_EXPECT(context, s_capture_length == 0U);

    TEST_EXPECT(context, Logger_SetLevel(LOG_LEVEL_DEBUG));
    TEST_EXPECT(context, !Logger_Write(LOG_LEVEL_INFO, "APP", NULL));

    ResetCapture();
    TEST_EXPECT(context, Logger_Write(LOG_LEVEL_ERROR, "", "failed"));
    TEST_EXPECT(context,
                memcmp(s_capture_buffer,
                       expected_general,
                       sizeof(expected_general) - 1U) == 0);

    ResetCapture();
    TEST_EXPECT(context, Logger_WriteFormatted(LOG_LEVEL_INFO, "TEST", "value=%u", 42U));
    TEST_EXPECT(context,
                memcmp(s_capture_buffer,
                       expected_formatted,
                       sizeof(expected_formatted) - 1U) == 0);

    (void)memset(long_message, 'A', sizeof(long_message));
    long_message[sizeof(long_message) - 1U] = '\0';
    ResetCapture();
    TEST_EXPECT(context, !Logger_Write(LOG_LEVEL_INFO, "TEST", long_message));
    TEST_EXPECT(context, s_capture_length == 0U);

    TEST_EXPECT(context, strcmp(Logger_LevelToString((LogLevel_t)99), "UNKNOWN") == 0);
    TEST_EXPECT(context, !Logger_Write((LogLevel_t)99, "TEST", "invalid"));
    TEST_EXPECT(context, !Logger_SetLevel((LogLevel_t)99));
    s_lock_success = false;
    TEST_EXPECT(context, !Logger_Write(LOG_LEVEL_INFO, "TEST", "locked"));
    TEST_EXPECT(context, s_unlock_count < s_lock_count);
    TEST_EXPECT(context, Logger_SetLock(NULL, NULL));
}
