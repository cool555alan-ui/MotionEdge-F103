#include "logger.h"

#include <stdarg.h>
#include <stdio.h>

#include "app_config.h"

static LogWriteFunction_t s_write_function = NULL;
static LogLevel_t s_minimum_level = LOG_LEVEL_NONE;
static char s_log_buffer[APP_LOG_BUFFER_SIZE];
static char s_message_buffer[APP_LOG_BUFFER_SIZE];

static bool Logger_IsThresholdValid(LogLevel_t level)
{
    return (level >= LOG_LEVEL_DEBUG) && (level <= LOG_LEVEL_NONE);
}

static bool Logger_IsMessageLevelValid(LogLevel_t level)
{
    return (level >= LOG_LEVEL_DEBUG) && (level <= LOG_LEVEL_ERROR);
}

static bool Logger_IsFiltered(LogLevel_t level)
{
    return (s_minimum_level == LOG_LEVEL_NONE) || (level < s_minimum_level);
}

bool Logger_Init(LogWriteFunction_t write_function, LogLevel_t minimum_level)
{
    if ((write_function == NULL) || !Logger_IsThresholdValid(minimum_level))
    {
        return false;
    }

    s_write_function = write_function;
    s_minimum_level = minimum_level;
    return true;
}

bool Logger_SetLevel(LogLevel_t minimum_level)
{
    if (!Logger_IsThresholdValid(minimum_level))
    {
        return false;
    }

    s_minimum_level = minimum_level;
    return true;
}

bool Logger_Write(LogLevel_t level, const char *module, const char *message)
{
    const char *effective_module = module;
    int written;

    if ((s_write_function == NULL) || !Logger_IsMessageLevelValid(level) ||
        (message == NULL))
    {
        return false;
    }
    if (Logger_IsFiltered(level))
    {
        return true;
    }
    if ((effective_module == NULL) || (effective_module[0] == '\0'))
    {
        effective_module = "GENERAL";
    }

    written = snprintf(s_log_buffer,
                       sizeof(s_log_buffer),
                       "[%s][%s] %s\r\n",
                       Logger_LevelToString(level),
                       effective_module,
                       message);
    if ((written < 0) || ((size_t)written >= sizeof(s_log_buffer)))
    {
        return false;
    }

    return s_write_function((const uint8_t *)s_log_buffer, (size_t)written);
}

bool Logger_WriteFormatted(LogLevel_t level, const char *module, const char *format, ...)
{
    va_list arguments;
    int written;

    if ((s_write_function == NULL) || !Logger_IsMessageLevelValid(level) ||
        (format == NULL))
    {
        return false;
    }
    if (Logger_IsFiltered(level))
    {
        return true;
    }

    va_start(arguments, format);
    written = vsnprintf(s_message_buffer, sizeof(s_message_buffer), format, arguments);
    va_end(arguments);
    if ((written < 0) || ((size_t)written >= sizeof(s_message_buffer)))
    {
        return false;
    }

    return Logger_Write(level, module, s_message_buffer);
}

const char *Logger_LevelToString(LogLevel_t level)
{
    switch (level)
    {
        case LOG_LEVEL_DEBUG:
            return "DEBUG";
        case LOG_LEVEL_INFO:
            return "INFO";
        case LOG_LEVEL_WARN:
            return "WARN";
        case LOG_LEVEL_ERROR:
            return "ERROR";
        case LOG_LEVEL_NONE:
            return "NONE";
        default:
            return "UNKNOWN";
    }
}
