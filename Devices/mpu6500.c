#include "mpu6500.h"

#include <stddef.h>

#define MPU6500_REGISTER_ACCEL_XOUT_H 0x3BU
#define MPU6500_REGISTER_PWR_MGMT_1 0x6BU
#define MPU6500_REGISTER_WHO_AM_I 0x75U
#define MPU6500_PWR_MGMT_1_WAKE_VALUE 0x00U
#define MPU6500_RAW_FRAME_SIZE 14U

static int16_t Mpu6500_DecodeSignedWord(uint8_t high_byte, uint8_t low_byte)
{
    uint16_t value = ((uint16_t)high_byte << 8U) | low_byte;

    if (value <= (uint16_t)INT16_MAX)
    {
        return (int16_t)value;
    }
    return (int16_t)((int32_t)value - 65536);
}

static bool Mpu6500_IsAddressValid(uint8_t address_7bit)
{
    return (address_7bit == MPU6500_ADDRESS_AD0_LOW) ||
           (address_7bit == MPU6500_ADDRESS_AD0_HIGH);
}

Mpu6500Status_t Mpu6500_Init(Mpu6500_t *device,
                             uint8_t address_7bit,
                             Mpu6500BusRead_t read_function,
                             Mpu6500BusWrite_t write_function)
{
    if ((device == NULL) || !Mpu6500_IsAddressValid(address_7bit) ||
        (read_function == NULL) || (write_function == NULL))
    {
        return MPU6500_ERROR_INVALID_ARG;
    }

    device->read = read_function;
    device->write = write_function;
    device->address = address_7bit;
    device->initialized = true;
    device->awake = false;
    return MPU6500_OK;
}

Mpu6500Status_t Mpu6500_ReadWhoAmI(Mpu6500_t *device, uint8_t *identity)
{
    if ((device == NULL) || (identity == NULL))
    {
        return MPU6500_ERROR_INVALID_ARG;
    }
    if (!device->initialized || (device->read == NULL))
    {
        return MPU6500_ERROR_NOT_INITIALIZED;
    }
    if (!device->read(device->address, MPU6500_REGISTER_WHO_AM_I, identity, 1U))
    {
        return MPU6500_ERROR_BUS;
    }

    return MPU6500_OK;
}

Mpu6500Status_t Mpu6500_VerifyIdentity(Mpu6500_t *device)
{
    uint8_t identity;
    Mpu6500Status_t status = Mpu6500_ReadWhoAmI(device, &identity);

    if (status != MPU6500_OK)
    {
        return status;
    }
    /* MPU6500的WHO_AM_I固定为0x70，与AD0选择的I²C地址无关。 */
    if (identity != MPU6500_WHO_AM_I_VALUE)
    {
        return MPU6500_ERROR_IDENTITY;
    }

    return MPU6500_OK;
}

Mpu6500Status_t Mpu6500_Wake(Mpu6500_t *device)
{
    const uint8_t wake_value = MPU6500_PWR_MGMT_1_WAKE_VALUE;

    if (device == NULL)
    {
        return MPU6500_ERROR_INVALID_ARG;
    }
    if (!device->initialized || (device->write == NULL))
    {
        return MPU6500_ERROR_NOT_INITIALIZED;
    }
    if (!device->write(
            device->address, MPU6500_REGISTER_PWR_MGMT_1, &wake_value, 1U))
    {
        return MPU6500_ERROR_BUS;
    }

    device->awake = true;
    return MPU6500_OK;
}

Mpu6500Status_t Mpu6500_ReadRaw(Mpu6500_t *device, Mpu6500RawData_t *raw_data)
{
    uint8_t frame[MPU6500_RAW_FRAME_SIZE];

    if ((device == NULL) || (raw_data == NULL))
    {
        return MPU6500_ERROR_INVALID_ARG;
    }
    if (!device->initialized || !device->awake || (device->read == NULL))
    {
        return MPU6500_ERROR_NOT_INITIALIZED;
    }
    if (!device->read(device->address,
                      MPU6500_REGISTER_ACCEL_XOUT_H,
                      frame,
                      sizeof(frame)))
    {
        return MPU6500_ERROR_BUS;
    }

    raw_data->accel_x = Mpu6500_DecodeSignedWord(frame[0], frame[1]);
    raw_data->accel_y = Mpu6500_DecodeSignedWord(frame[2], frame[3]);
    raw_data->accel_z = Mpu6500_DecodeSignedWord(frame[4], frame[5]);
    raw_data->gyro_x = Mpu6500_DecodeSignedWord(frame[8], frame[9]);
    raw_data->gyro_y = Mpu6500_DecodeSignedWord(frame[10], frame[11]);
    raw_data->gyro_z = Mpu6500_DecodeSignedWord(frame[12], frame[13]);
    return MPU6500_OK;
}


bool Mpu6500_ScaleRaw(const Mpu6500RawData_t *raw_data,
                      Mpu6500ScaledSample_t *scaled_sample)
{
    if ((raw_data == NULL) || (scaled_sample == NULL))
    {
        return false;
    }

    /* MPU6500复位默认量程：加速度16384 LSB/g，角速度131 LSB/(deg/s)。 */
    scaled_sample->accel_mg_x = ((int32_t)raw_data->accel_x * 1000) / 16384;
    scaled_sample->accel_mg_y = ((int32_t)raw_data->accel_y * 1000) / 16384;
    scaled_sample->accel_mg_z = ((int32_t)raw_data->accel_z * 1000) / 16384;
    scaled_sample->gyro_mdps_x = ((int32_t)raw_data->gyro_x * 1000) / 131;
    scaled_sample->gyro_mdps_y = ((int32_t)raw_data->gyro_y * 1000) / 131;
    scaled_sample->gyro_mdps_z = ((int32_t)raw_data->gyro_z * 1000) / 131;
    return true;
}
