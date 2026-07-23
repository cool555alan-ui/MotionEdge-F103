#include "i2c_scanner.h"

#include <stddef.h>

bool I2cScanner_Init(I2cScanner_t *scanner, I2cProbeFunction_t probe_function)
{
    if ((scanner == NULL) || (probe_function == NULL))
    {
        return false;
    }

    scanner->probe_function = probe_function;
    scanner->next_address = I2C_SCANNER_FIRST_ADDRESS;
    scanner->found_count = 0U;
    scanner->initialized = true;
    scanner->complete = false;
    return true;
}

bool I2cScanner_Step(I2cScanner_t *scanner, I2cScanStepResult_t *result)
{
    if ((scanner == NULL) || (result == NULL) || !scanner->initialized ||
        scanner->complete || (scanner->probe_function == NULL))
    {
        return false;
    }

    result->address = scanner->next_address;
    result->responded = scanner->probe_function(scanner->next_address);
    if (result->responded)
    {
        ++scanner->found_count;
    }

    if (scanner->next_address == I2C_SCANNER_LAST_ADDRESS)
    {
        scanner->complete = true;
    }
    else
    {
        ++scanner->next_address;
    }
    result->complete = scanner->complete;
    return true;
}
