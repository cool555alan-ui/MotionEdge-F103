#include "bsp_uart.h"

#include <stdint.h>

#include "app_config.h"
#include "usart.h"

static bool s_uart_ready = false;

BspUartStatus_t BspUart_Init(void)
{
    if (huart1.Instance != USART1)
    {
        s_uart_ready = false;
        return BSP_UART_ERROR_NOT_READY;
    }

    s_uart_ready = true;
    return BSP_UART_OK;
}

BspUartStatus_t BspUart_Write(const uint8_t *data, size_t length)
{
    HAL_StatusTypeDef hal_status;

    if (length == 0U)
    {
        return BSP_UART_OK;
    }
    if (data == NULL)
    {
        return BSP_UART_ERROR_INVALID_ARG;
    }
    if (!s_uart_ready)
    {
        return BSP_UART_ERROR_NOT_READY;
    }
    if (length > UINT16_MAX)
    {
        return BSP_UART_ERROR_INVALID_ARG;
    }

    /* The upper bound check makes the conversion to the HAL length type safe. */
    hal_status = HAL_UART_Transmit(&huart1, data, (uint16_t)length, APP_UART_TIMEOUT_MS);
    switch (hal_status)
    {
        case HAL_OK:
            return BSP_UART_OK;
        case HAL_TIMEOUT:
            return BSP_UART_ERROR_TIMEOUT;
        case HAL_BUSY:
            return BSP_UART_ERROR_NOT_READY;
        default:
            return BSP_UART_ERROR_HAL;
    }
}

bool BspUart_IsReady(void)
{
    return s_uart_ready;
}
