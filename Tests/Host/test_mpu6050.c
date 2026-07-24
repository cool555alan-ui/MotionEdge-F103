#include <string.h>

#include "mpu6050.h"
#include "test_support.h"

static uint8_t s_identity = MPU6050_WHO_AM_I_VALUE;
static uint8_t s_raw_frame[14];
static bool s_read_success = true;
static bool s_write_success = true;
static uint8_t s_write_address = 0U;
static uint8_t s_write_register = 0U;
static uint8_t s_write_value = 0U;
static size_t s_write_length = 0U;

static bool MockRead(uint8_t address_7bit,
                     uint8_t register_address,
                     uint8_t *data,
                     size_t length)
{
    if (!s_read_success || (address_7bit != MPU6050_ADDRESS_AD0_LOW) ||
        (data == NULL))
    {
        return false;
    }
    if ((register_address == 0x75U) && (length == 1U))
    {
        data[0] = s_identity;
        return true;
    }
    if ((register_address == 0x3BU) && (length == sizeof(s_raw_frame)))
    {
        (void)memcpy(data, s_raw_frame, sizeof(s_raw_frame));
        return true;
    }
    return false;
}

static bool MockWrite(uint8_t address_7bit,
                      uint8_t register_address,
                      const uint8_t *data,
                      size_t length)
{
    if (!s_write_success || (data == NULL) || (length == 0U))
    {
        return false;
    }

    s_write_address = address_7bit;
    s_write_register = register_address;
    s_write_value = data[0];
    s_write_length = length;
    return true;
}

void TestMpu6050_Run(TestContext_t *context)
{
    Mpu6050_t device = {0};
    Mpu6050RawData_t raw_data = {0};
    Mpu6050ScaledSample_t scaled_sample = {0};
    uint8_t identity = 0U;

    TEST_EXPECT(context,
                Mpu6050_Init(NULL,
                             MPU6050_ADDRESS_AD0_LOW,
                             MockRead,
                             MockWrite) == MPU6050_ERROR_INVALID_ARG);
    TEST_EXPECT(context,
                Mpu6050_Init(&device, 0x67U, MockRead, MockWrite) ==
                    MPU6050_ERROR_INVALID_ARG);
    TEST_EXPECT(context,
                Mpu6050_Init(&device,
                             MPU6050_ADDRESS_AD0_LOW,
                             NULL,
                             MockWrite) == MPU6050_ERROR_INVALID_ARG);
    TEST_EXPECT(context,
                Mpu6050_ReadWhoAmI(&device, &identity) ==
                    MPU6050_ERROR_NOT_INITIALIZED);
    TEST_EXPECT(context,
                Mpu6050_Init(&device,
                             MPU6050_ADDRESS_AD0_LOW,
                             MockRead,
                             MockWrite) == MPU6050_OK);

    s_identity = MPU6050_WHO_AM_I_VALUE;
    s_read_success = true;
    TEST_EXPECT(context, Mpu6050_ReadWhoAmI(&device, &identity) == MPU6050_OK);
    TEST_EXPECT(context, identity == MPU6050_WHO_AM_I_VALUE);
    TEST_EXPECT(context, Mpu6050_VerifyIdentity(&device) == MPU6050_OK);
    s_identity = 0x69U;
    TEST_EXPECT(context, Mpu6050_VerifyIdentity(&device) == MPU6050_OK);
    s_identity = 0x00U;
    TEST_EXPECT(context, Mpu6050_VerifyIdentity(&device) == MPU6050_ERROR_IDENTITY);
    s_identity = MPU6050_WHO_AM_I_VALUE;

    TEST_EXPECT(context,
                Mpu6050_ReadRaw(&device, &raw_data) ==
                    MPU6050_ERROR_NOT_INITIALIZED);
    s_write_success = true;
    TEST_EXPECT(context, Mpu6050_Wake(&device) == MPU6050_OK);
    TEST_EXPECT(context, device.awake);
    TEST_EXPECT(context, s_write_address == MPU6050_ADDRESS_AD0_LOW);
    TEST_EXPECT(context, s_write_register == 0x6BU);
    TEST_EXPECT(context, s_write_value == 0x00U);
    TEST_EXPECT(context, s_write_length == 1U);

    {
        const uint8_t expected_frame[14] = {
            0x12U, 0x34U, 0xFFU, 0xFFU, 0x80U, 0x00U, 0x00U,
            0x00U, 0x7FU, 0xFFU, 0xFEU, 0xDCU, 0x00U, 0x01U};
        (void)memcpy(s_raw_frame, expected_frame, sizeof(s_raw_frame));
    }
    TEST_EXPECT(context, Mpu6050_ReadRaw(&device, &raw_data) == MPU6050_OK);
    TEST_EXPECT(context, raw_data.accel_x == 4660);
    TEST_EXPECT(context, raw_data.accel_y == -1);
    TEST_EXPECT(context, raw_data.accel_z == INT16_MIN);
    TEST_EXPECT(context, raw_data.gyro_x == INT16_MAX);
    TEST_EXPECT(context, raw_data.gyro_y == -292);
    TEST_EXPECT(context, raw_data.gyro_z == 1);

    s_read_success = false;
    TEST_EXPECT(context, Mpu6050_ReadWhoAmI(&device, &identity) == MPU6050_ERROR_BUS);
    TEST_EXPECT(context, Mpu6050_ReadRaw(&device, &raw_data) == MPU6050_ERROR_BUS);
    s_read_success = true;
    s_write_success = false;
    TEST_EXPECT(context, Mpu6050_Wake(&device) == MPU6050_ERROR_BUS);
    TEST_EXPECT(context,
                Mpu6050_ReadRaw(&device, NULL) == MPU6050_ERROR_INVALID_ARG);
    raw_data =
        (Mpu6050RawData_t){16384, -16384, 8192, 131, -131, 262};
    TEST_EXPECT(context, Mpu6050_ScaleRaw(&raw_data, &scaled_sample));
    TEST_EXPECT(context, scaled_sample.accel_mg_x == 1000);
    TEST_EXPECT(context, scaled_sample.accel_mg_y == -1000);
    TEST_EXPECT(context, scaled_sample.accel_mg_z == 500);
    TEST_EXPECT(context, scaled_sample.gyro_mdps_x == 1000);
    TEST_EXPECT(context, scaled_sample.gyro_mdps_y == -1000);
    TEST_EXPECT(context, scaled_sample.gyro_mdps_z == 2000);
    TEST_EXPECT(context, !Mpu6050_ScaleRaw(NULL, &scaled_sample));
}
