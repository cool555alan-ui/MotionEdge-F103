#ifndef MPU6050_H
#define MPU6050_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define MPU6050_ADDRESS_AD0_LOW 0x68U
#define MPU6050_ADDRESS_AD0_HIGH 0x69U
#define MPU6050_WHO_AM_I_VALUE 0x68U

typedef bool (*Mpu6050BusRead_t)(uint8_t address_7bit,
                                uint8_t register_address,
                                uint8_t *data,
                                size_t length);
typedef bool (*Mpu6050BusWrite_t)(uint8_t address_7bit,
                                 uint8_t register_address,
                                 const uint8_t *data,
                                 size_t length);

typedef enum
{
    MPU6050_OK = 0,
    MPU6050_ERROR_INVALID_ARG,
    MPU6050_ERROR_NOT_INITIALIZED,
    MPU6050_ERROR_BUS,
    MPU6050_ERROR_IDENTITY
} Mpu6050Status_t;

typedef struct
{
    int16_t accel_x;
    int16_t accel_y;
    int16_t accel_z;
    int16_t gyro_x;
    int16_t gyro_y;
    int16_t gyro_z;
} Mpu6050RawData_t;

typedef struct
{
    int32_t accel_mg_x;
    int32_t accel_mg_y;
    int32_t accel_mg_z;
    int32_t gyro_mdps_x;
    int32_t gyro_mdps_y;
    int32_t gyro_mdps_z;
} Mpu6050ScaledSample_t;

typedef struct
{
    Mpu6050BusRead_t read;
    Mpu6050BusWrite_t write;
    uint8_t address;
    bool initialized;
    bool awake;
} Mpu6050_t;

Mpu6050Status_t Mpu6050_Init(Mpu6050_t *device,
                             uint8_t address_7bit,
                             Mpu6050BusRead_t read_function,
                             Mpu6050BusWrite_t write_function);
Mpu6050Status_t Mpu6050_ReadWhoAmI(Mpu6050_t *device, uint8_t *identity);
Mpu6050Status_t Mpu6050_VerifyIdentity(Mpu6050_t *device);
Mpu6050Status_t Mpu6050_Wake(Mpu6050_t *device);
Mpu6050Status_t Mpu6050_ReadRaw(Mpu6050_t *device, Mpu6050RawData_t *raw_data);

/** 按默认±2 g和±250 dps量程将原始值转换为mg和mdps。 */
bool Mpu6050_ScaleRaw(const Mpu6050RawData_t *raw_data,
                      Mpu6050ScaledSample_t *scaled_sample);

#endif /* MPU6050_H */
