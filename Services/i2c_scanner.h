#ifndef I2C_SCANNER_H
#define I2C_SCANNER_H

#include <stdbool.h>
#include <stdint.h>

#define I2C_SCANNER_FIRST_ADDRESS 0x08U
#define I2C_SCANNER_LAST_ADDRESS 0x77U

typedef bool (*I2cProbeFunction_t)(uint8_t address_7bit);

typedef struct
{
    uint8_t address;
    bool responded;
    bool complete;
} I2cScanStepResult_t;

typedef struct
{
    I2cProbeFunction_t probe_function;
    uint8_t next_address;
    uint8_t found_count;
    bool initialized;
    bool complete;
} I2cScanner_t;

bool I2cScanner_Init(I2cScanner_t *scanner, I2cProbeFunction_t probe_function);
bool I2cScanner_Step(I2cScanner_t *scanner, I2cScanStepResult_t *result);

#endif /* I2C_SCANNER_H */
