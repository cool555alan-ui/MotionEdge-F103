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
BspUartStatus_t BspUart_TryReadByte(uint8_t *byte, bool *received);
/** 由USART1中断入口调用，HAL细节保持在BSP内。 */
void BspUart_IrqHandler(void);
/** 返回中断接收环形缓冲累计溢出次数。 */
uint32_t BspUart_GetRxOverflowCount(void);

#endif /* BSP_UART_H */
