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

typedef struct
{
    uint32_t parity_count;
    uint32_t noise_count;
    uint32_t framing_count;
    uint32_t overrun_count;
} BspUartRxErrorStats_t;

BspUartStatus_t BspUart_Init(void);
BspUartStatus_t BspUart_Write(const uint8_t *data, size_t length);
bool BspUart_IsReady(void);
BspUartStatus_t BspUart_TryReadByte(uint8_t *byte, bool *received);
/** 由USART1中断入口调用；普通字节由DMA接收，此处只处理线路错误。 */
void BspUart_IrqHandler(void);
/** 返回DMA固定缓冲区累计溢出的字节数。 */
uint32_t BspUart_GetRxOverflowCount(void);
/** 返回USART接收线路错误累计次数。 */
uint32_t BspUart_GetRxErrorCount(void);
/** 返回分类接收错误，供实机串口完整性诊断。 */
bool BspUart_GetRxErrorStats(BspUartRxErrorStats_t *stats);

#endif /* BSP_UART_H */
