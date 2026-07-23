#ifndef LOGGER_H
#define LOGGER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum
{
    LOG_LEVEL_DEBUG = 0,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARN,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_NONE
} LogLevel_t;

typedef bool (*LogWriteFunction_t)(const uint8_t *data, size_t length);

bool Logger_Init(LogWriteFunction_t write_function, LogLevel_t minimum_level);
bool Logger_SetLevel(LogLevel_t minimum_level);
bool Logger_Write(LogLevel_t level, const char *module, const char *message);
bool Logger_WriteFormatted(LogLevel_t level, const char *module, const char *format, ...);
const char *Logger_LevelToString(LogLevel_t level);

#endif /* LOGGER_H */
