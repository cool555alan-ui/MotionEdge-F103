#ifndef BSP_UART_H
#define BSP_UART_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum
{
    BSP_UART_OK = 0,
    BSP_UART_ERROR_INVALID_ARG,
    BSP_UART_ERROR_NOT_READY,
    BSP_UART_ERROR_TIMEOUT,
    BSP_UART_ERROR_HAL
} BspUartStatus_t;

BspUartStatus_t BspUart_Init(void);
BspUartStatus_t BspUart_Write(const uint8_t *data, size_t length);
bool BspUart_IsReady(void);

#endif /* BSP_UART_H */
