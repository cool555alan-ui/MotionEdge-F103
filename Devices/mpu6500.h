#ifndef MPU6500_H
#define MPU6500_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define MPU6500_ADDRESS_AD0_LOW 0x68U
#define MPU6500_ADDRESS_AD0_HIGH 0x69U
#define MPU6050_WHO_AM_I_VALUE 0x68U
#define MPU6500_WHO_AM_I_VALUE 0x70U

typedef enum
{
    MPU6XXX_MODEL_UNKNOWN = 0,
    MPU6XXX_MODEL_MPU6050,
    MPU6XXX_MODEL_MPU6500
} Mpu6xxxModel_t;

typedef bool (*Mpu6500BusRead_t)(uint8_t address_7bit,
                                uint8_t register_address,
                                uint8_t *data,
                                size_t length);
typedef bool (*Mpu6500BusWrite_t)(uint8_t address_7bit,
                                 uint8_t register_address,
                                 const uint8_t *data,
                                 size_t length);

typedef enum
{
    MPU6500_OK = 0,
    MPU6500_ERROR_INVALID_ARG,
    MPU6500_ERROR_NOT_INITIALIZED,
    MPU6500_ERROR_BUS,
    MPU6500_ERROR_IDENTITY
} Mpu6500Status_t;

typedef struct
{
    int16_t accel_x;
    int16_t accel_y;
    int16_t accel_z;
    int16_t gyro_x;
    int16_t gyro_y;
    int16_t gyro_z;
} Mpu6500RawData_t;

typedef struct
{
    int32_t accel_mg_x;
    int32_t accel_mg_y;
    int32_t accel_mg_z;
    int32_t gyro_mdps_x;
    int32_t gyro_mdps_y;
    int32_t gyro_mdps_z;
} Mpu6500ScaledSample_t;

typedef struct
{
    Mpu6500BusRead_t read;
    Mpu6500BusWrite_t write;
    uint8_t address;
    uint8_t identity;
    Mpu6xxxModel_t model;
    bool initialized;
    bool awake;
} Mpu6500_t;

Mpu6500Status_t Mpu6500_Init(Mpu6500_t *device,
                             uint8_t address_7bit,
                             Mpu6500BusRead_t read_function,
                             Mpu6500BusWrite_t write_function);
Mpu6500Status_t Mpu6500_ReadWhoAmI(Mpu6500_t *device, uint8_t *identity);
Mpu6500Status_t Mpu6500_VerifyIdentity(Mpu6500_t *device);
/** 根据WHO_AM_I区分兼容的MPU6050和MPU6500。 */
Mpu6xxxModel_t Mpu6500_DetectModel(uint8_t identity);
/** 返回设备识别结果的稳定文本。 */
const char *Mpu6500_ModelToString(Mpu6xxxModel_t model);
Mpu6500Status_t Mpu6500_Wake(Mpu6500_t *device);
Mpu6500Status_t Mpu6500_ReadRaw(Mpu6500_t *device, Mpu6500RawData_t *raw_data);

/** 按默认±2 g和±250 dps量程将原始值转换为mg和mdps。 */
bool Mpu6500_ScaleRaw(const Mpu6500RawData_t *raw_data,
                      Mpu6500ScaledSample_t *scaled_sample);

#endif /* MPU6500_H */
