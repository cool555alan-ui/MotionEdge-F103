#ifndef BSP_I2C_H
#define BSP_I2C_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum
{
    BSP_I2C_OK = 0,
    BSP_I2C_ERROR_INVALID_ARG,
    BSP_I2C_ERROR_NOT_READY,
    BSP_I2C_ERROR_TIMEOUT,
    BSP_I2C_ERROR_NO_ACK,
    BSP_I2C_ERROR_HAL
} BspI2cStatus_t;

BspI2cStatus_t BspI2c_Init(void);
BspI2cStatus_t BspI2c_RecoverBus(void);
BspI2cStatus_t BspI2c_IsDeviceReady(uint8_t address_7bit);
BspI2cStatus_t BspI2c_ReadRegister(uint8_t address_7bit,
                                  uint8_t register_address,
                                  uint8_t *data,
                                  size_t length);
BspI2cStatus_t BspI2c_WriteRegister(uint8_t address_7bit,
                                   uint8_t register_address,
                                   const uint8_t *data,
                                   size_t length);
bool BspI2c_IsReady(void);

#endif /* BSP_I2C_H */
