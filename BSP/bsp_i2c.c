#include "bsp_i2c.h"

#include <limits.h>

#include "app_config.h"
#include "i2c.h"

#define BSP_I2C_RECOVERY_CLOCK_PULSES 9U
#define BSP_I2C_RECOVERY_DELAY_CYCLES 360U

static bool s_i2c_ready = false;

static void BspI2c_RecoveryDelay(void)
{
    volatile uint32_t cycle;

    for (cycle = 0U; cycle < BSP_I2C_RECOVERY_DELAY_CYCLES; ++cycle)
    {
        __NOP();
    }
}

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

    return BspI2c_RecoverBus();
}

BspI2cStatus_t BspI2c_RecoverBus(void)
{
    GPIO_InitTypeDef gpio = {0};
    uint32_t pulse;
    bool lines_released;

    if (hi2c1.Instance != I2C1)
    {
        s_i2c_ready = false;
        return BSP_I2C_ERROR_NOT_READY;
    }

    s_i2c_ready = false;
    if (HAL_I2C_DeInit(&hi2c1) != HAL_OK)
    {
        return BSP_I2C_ERROR_HAL;
    }

    __HAL_RCC_GPIOB_CLK_ENABLE();
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_6 | GPIO_PIN_7, GPIO_PIN_SET);
    gpio.Pin = GPIO_PIN_6 | GPIO_PIN_7;
    gpio.Mode = GPIO_MODE_OUTPUT_OD;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOB, &gpio);
    BspI2c_RecoveryDelay();

    /* MCU在从机发送过程中复位时，补齐最多9个时钟以释放SDA。 */
    for (pulse = 0U;
         (pulse < BSP_I2C_RECOVERY_CLOCK_PULSES) &&
         (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_7) == GPIO_PIN_RESET);
         ++pulse)
    {
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_6, GPIO_PIN_RESET);
        BspI2c_RecoveryDelay();
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_6, GPIO_PIN_SET);
        BspI2c_RecoveryDelay();
    }

    /* 显式产生STOP，确保从机结束被复位打断的事务。 */
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_7, GPIO_PIN_RESET);
    BspI2c_RecoveryDelay();
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_6, GPIO_PIN_SET);
    BspI2c_RecoveryDelay();
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_7, GPIO_PIN_SET);
    BspI2c_RecoveryDelay();
    lines_released =
        (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_6) == GPIO_PIN_SET) &&
        (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_7) == GPIO_PIN_SET);

    if (HAL_I2C_Init(&hi2c1) != HAL_OK)
    {
        return BSP_I2C_ERROR_HAL;
    }
    if (!lines_released)
    {
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
    if (!s_i2c_ready && (BspI2c_RecoverBus() != BSP_I2C_OK))
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
    if (!s_i2c_ready && (BspI2c_RecoverBus() != BSP_I2C_OK))
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
    if ((hal_status != HAL_OK) && (BspI2c_RecoverBus() == BSP_I2C_OK))
    {
        /* 单次恢复后重试，避免瞬时总线卡死演变为永久降级。 */
        hal_status = HAL_I2C_Mem_Read(&hi2c1,
                                     (uint16_t)address_7bit << 1U,
                                     register_address,
                                     I2C_MEMADD_SIZE_8BIT,
                                     data,
                                     (uint16_t)length,
                                     APP_I2C_TRANSFER_TIMEOUT_MS);
    }
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
    if (!s_i2c_ready && (BspI2c_RecoverBus() != BSP_I2C_OK))
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
    if ((hal_status != HAL_OK) && (BspI2c_RecoverBus() == BSP_I2C_OK))
    {
        hal_status = HAL_I2C_Mem_Write(&hi2c1,
                                      (uint16_t)address_7bit << 1U,
                                      register_address,
                                      I2C_MEMADD_SIZE_8BIT,
                                      (uint8_t *)data,
                                      (uint16_t)length,
                                      APP_I2C_TRANSFER_TIMEOUT_MS);
    }
    return BspI2c_MapHalStatus(hal_status);
}

bool BspI2c_IsReady(void)
{
    return s_i2c_ready;
}
