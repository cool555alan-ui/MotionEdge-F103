#include "bsp_i2c.h"

#include <limits.h>

#include "app_config.h"
#include "i2c.h"

static bool s_i2c_ready = false;

static bool BspI2c_IsAddressValid(uint8_t address_7bit)
{
    return (address_7bit >= 0x08U) && (address_7bit <= 0x77U);
}

static BspI2cStatus_t BspI2c_MapHalStatus(HAL_StatusTypeDef hal_status)
{
    switch (hal_status)
    {
        case HAL_OK:
            return BSP_I2C_OK;
        case HAL_TIMEOUT:
            return BSP_I2C_ERROR_TIMEOUT;
        case HAL_BUSY:
            return BSP_I2C_ERROR_NOT_READY;
        default:
            if ((HAL_I2C_GetError(&hi2c1) & HAL_I2C_ERROR_AF) != 0U)
            {
                return BSP_I2C_ERROR_NO_ACK;
            }
            return BSP_I2C_ERROR_HAL;
    }
}

BspI2cStatus_t BspI2c_Init(void)
{
    if (hi2c1.Instance != I2C1)
    {
        s_i2c_ready = false;
        return BSP_I2C_ERROR_NOT_READY;
    }

    s_i2c_ready = true;
    return BSP_I2C_OK;
}

BspI2cStatus_t BspI2c_IsDeviceReady(uint8_t address_7bit)
{
    HAL_StatusTypeDef hal_status;

    if (!BspI2c_IsAddressValid(address_7bit))
    {
        return BSP_I2C_ERROR_INVALID_ARG;
    }
    if (!s_i2c_ready)
    {
        return BSP_I2C_ERROR_NOT_READY;
    }

    hal_status = HAL_I2C_IsDeviceReady(
        &hi2c1, (uint16_t)address_7bit << 1U, 1U, APP_I2C_PROBE_TIMEOUT_MS);
    return BspI2c_MapHalStatus(hal_status);
}

BspI2cStatus_t BspI2c_ReadRegister(uint8_t address_7bit,
                                  uint8_t register_address,
                                  uint8_t *data,
                                  size_t length)
{
    HAL_StatusTypeDef hal_status;

    if (!BspI2c_IsAddressValid(address_7bit) || (data == NULL) || (length == 0U) ||
        (length > UINT16_MAX))
    {
        return BSP_I2C_ERROR_INVALID_ARG;
    }
    if (!s_i2c_ready)
    {
        return BSP_I2C_ERROR_NOT_READY;
    }

    hal_status = HAL_I2C_Mem_Read(&hi2c1,
                                 (uint16_t)address_7bit << 1U,
                                 register_address,
                                 I2C_MEMADD_SIZE_8BIT,
                                 data,
                                 (uint16_t)length,
                                 APP_I2C_TRANSFER_TIMEOUT_MS);
    return BspI2c_MapHalStatus(hal_status);
}

BspI2cStatus_t BspI2c_WriteRegister(uint8_t address_7bit,
                                   uint8_t register_address,
                                   const uint8_t *data,
                                   size_t length)
{
    HAL_StatusTypeDef hal_status;

    if (!BspI2c_IsAddressValid(address_7bit) || (data == NULL) || (length == 0U) ||
        (length > UINT16_MAX))
    {
        return BSP_I2C_ERROR_INVALID_ARG;
    }
    if (!s_i2c_ready)
    {
        return BSP_I2C_ERROR_NOT_READY;
    }

    /*
     * STM32 HAL does not declare its transmit buffer const. The HAL call does
     * not modify the supplied bytes, so the adapter contains the cast here.
     */
    hal_status = HAL_I2C_Mem_Write(&hi2c1,
                                  (uint16_t)address_7bit << 1U,
                                  register_address,
                                  I2C_MEMADD_SIZE_8BIT,
                                  (uint8_t *)data,
                                  (uint16_t)length,
                                  APP_I2C_TRANSFER_TIMEOUT_MS);
    return BspI2c_MapHalStatus(hal_status);
}

bool BspI2c_IsReady(void)
{
    return s_i2c_ready;
}
