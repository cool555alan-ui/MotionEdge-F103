#include "i2c_scanner.h"
#include "mpu6500.h"
#include "test_support.h"

static uint32_t s_probe_count = 0U;
static uint8_t s_last_probe_address = 0U;

static bool TestProbe(uint8_t address_7bit)
{
    ++s_probe_count;
    s_last_probe_address = address_7bit;
    return (address_7bit == 0x3CU) || (address_7bit == MPU6500_ADDRESS_AD0_LOW);
}

void TestI2cScanner_Run(TestContext_t *context)
{
    I2cScanner_t scanner = {0};
    I2cScanStepResult_t result = {0};
    uint32_t expected_probe_count =
        (uint32_t)I2C_SCANNER_LAST_ADDRESS - I2C_SCANNER_FIRST_ADDRESS + 1U;

    s_probe_count = 0U;
    s_last_probe_address = 0U;

    TEST_EXPECT(context, !I2cScanner_Init(NULL, TestProbe));
    TEST_EXPECT(context, !I2cScanner_Init(&scanner, NULL));
    TEST_EXPECT(context, !I2cScanner_Step(NULL, &result));
    TEST_EXPECT(context, !I2cScanner_Step(&scanner, &result));
    TEST_EXPECT(context, I2cScanner_Init(&scanner, TestProbe));
    TEST_EXPECT(context, scanner.next_address == I2C_SCANNER_FIRST_ADDRESS);

    while (!scanner.complete)
    {
        TEST_EXPECT(context, I2cScanner_Step(&scanner, &result));
        if (result.address == 0x3CU)
        {
            TEST_EXPECT(context, result.responded);
        }
    }

    TEST_EXPECT(context, result.address == I2C_SCANNER_LAST_ADDRESS);
    TEST_EXPECT(context, result.complete);
    TEST_EXPECT(context, scanner.found_count == 2U);
    TEST_EXPECT(context, s_probe_count == expected_probe_count);
    TEST_EXPECT(context, s_last_probe_address == I2C_SCANNER_LAST_ADDRESS);
    TEST_EXPECT(context, !I2cScanner_Step(&scanner, &result));
}
