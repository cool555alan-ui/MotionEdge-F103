#ifndef CSV_TELEMETRY_H
#define CSV_TELEMETRY_H

#include <stdbool.h>
#include <stddef.h>

#include "motion_service.h"

/** 写入固定CSV表头，行尾为CRLF。 */
bool CsvTelemetry_WriteHeader(char *buffer, size_t capacity, size_t *written);

/** 将运动帧序列化为全整数CSV行。 */
bool CsvTelemetry_WriteFrame(const MotionFrame_t *frame,
                             char *buffer,
                             size_t capacity,
                             size_t *written);

#endif /* CSV_TELEMETRY_H */
