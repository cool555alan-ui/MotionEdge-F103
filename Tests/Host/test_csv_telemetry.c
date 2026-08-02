#include <string.h>

#include "csv_telemetry.h"
#include "test_support.h"

void TestCsvTelemetry_Run(TestContext_t *context)
{
    char buffer[256];
    size_t written = 99U;
    MotionFrame_t frame = {0};
    const char header[] =
        "timestamp_ms,sequence,status_flags,calibrated,"
        "ax_mg,ay_mg,az_mg,gx_mdps,gy_mdps,gz_mdps,"
        "roll_cdeg,pitch_cdeg\r\n";
    const char expected[] = "123,7,5,1,-10,20,1000,-1,2,-3,125,-340\r\n";

    TEST_EXPECT(context, !CsvTelemetry_WriteHeader(NULL, sizeof(buffer), &written));
    TEST_EXPECT(context, !CsvTelemetry_WriteHeader(buffer, sizeof(buffer), NULL));
    TEST_EXPECT(context, !CsvTelemetry_WriteHeader(buffer, 0U, &written));
    TEST_EXPECT(context, CsvTelemetry_WriteHeader(buffer, sizeof(buffer), &written));
    TEST_EXPECT(context, written == (sizeof(header) - 1U));
    TEST_EXPECT(context, strcmp(buffer, header) == 0);
    TEST_EXPECT(context, !CsvTelemetry_WriteHeader(buffer, sizeof(header) - 1U, &written));
    TEST_EXPECT(context, written == 0U);
    frame.timestamp_ms = 123U;
    frame.sequence = 7U;
    frame.status_flags = 5U;
    frame.calibrated = true;
    frame.filtered = (Mpu6500ScaledSample_t){-10, 20, 1000, -1, 2, -3};
    frame.attitude.roll_cdeg = 125;
    frame.attitude.pitch_cdeg = -340;
    frame.attitude.valid = true;
    frame.valid = true;
    TEST_EXPECT(context, CsvTelemetry_WriteFrame(&frame, buffer, sizeof(buffer), &written));
    TEST_EXPECT(context, written == (sizeof(expected) - 1U));
    TEST_EXPECT(context, strcmp(buffer, expected) == 0);
    TEST_EXPECT(context,
                !CsvTelemetry_WriteFrame(&frame, buffer, sizeof(expected) - 1U, &written));
    TEST_EXPECT(context, written == 0U);
    frame.valid = false;
    TEST_EXPECT(context, !CsvTelemetry_WriteFrame(&frame, buffer, sizeof(buffer), &written));
    TEST_EXPECT(context, !CsvTelemetry_WriteFrame(NULL, buffer, sizeof(buffer), &written));
}
