#include "csv_telemetry.h"

#include <inttypes.h>
#include <stdio.h>

static const char s_csv_header[] =
    "timestamp_ms,sequence,status_flags,calibrated,"
    "ax_mg,ay_mg,az_mg,gx_mdps,gy_mdps,gz_mdps,"
    "roll_cdeg,pitch_cdeg\r\n";

bool CsvTelemetry_WriteHeader(char *buffer, size_t capacity, size_t *written)
{
    int result;

    if ((buffer == NULL) || (written == NULL) || (capacity == 0U))
    {
        return false;
    }
    *written = 0U;
    result = snprintf(buffer, capacity, "%s", s_csv_header);
    if ((result < 0) || ((size_t)result >= capacity))
    {
        return false;
    }
    *written = (size_t)result;
    return true;
}

bool CsvTelemetry_WriteFrame(const MotionFrame_t *frame,
                             char *buffer,
                             size_t capacity,
                             size_t *written)
{
    int result;

    if ((frame == NULL) || (buffer == NULL) || (written == NULL) ||
        (capacity == 0U) || !frame->valid || !frame->attitude.valid)
    {
        return false;
    }
    *written = 0U;
    result = snprintf(buffer,
                      capacity,
                      "%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%u,"
                      "%" PRId32 ",%" PRId32 ",%" PRId32 ","
                      "%" PRId32 ",%" PRId32 ",%" PRId32 ","
                      "%" PRId32 ",%" PRId32 "\r\n",
                      frame->timestamp_ms,
                      frame->sequence,
                      frame->status_flags,
                      frame->calibrated ? 1U : 0U,
                      frame->filtered.accel_mg_x,
                      frame->filtered.accel_mg_y,
                      frame->filtered.accel_mg_z,
                      frame->filtered.gyro_mdps_x,
                      frame->filtered.gyro_mdps_y,
                      frame->filtered.gyro_mdps_z,
                      frame->attitude.roll_cdeg,
                      frame->attitude.pitch_cdeg);
    if ((result < 0) || ((size_t)result >= capacity))
    {
        return false;
    }
    *written = (size_t)result;
    return true;
}
