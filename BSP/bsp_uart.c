#include "bsp_uart.h"

#include <stdint.h>

#include "app_config.h"
#include "usart.h"

#define BSP_UART_RX_DMA_CAPACITY 512U

static bool s_uart_ready = false;
static uint8_t s_rx_dma_storage[BSP_UART_RX_DMA_CAPACITY];
static uint16_t s_rx_dma_read_index;
static uint16_t s_rx_dma_last_write_index;
static uint32_t s_rx_dma_pending_count;
static volatile uint32_t s_rx_overflow_count;
static volatile uint32_t s_rx_error_count;
static volatile uint32_t s_rx_parity_error_count;
static volatile uint32_t s_rx_noise_error_count;
static volatile uint32_t s_rx_framing_error_count;
static volatile uint32_t s_rx_overrun_error_count;

static bool StartRxDma(void)
{
    if ((huart1.hdmarx == NULL) ||
        (huart1.hdmarx->Init.Mode != DMA_CIRCULAR) ||
        (HAL_UART_Receive_DMA(&huart1,
                              s_rx_dma_storage,
                              BSP_UART_RX_DMA_CAPACITY) != HAL_OK))
    {
        return false;
    }

    s_rx_dma_read_index = 0U;
    s_rx_dma_last_write_index = 0U;
    s_rx_dma_pending_count = 0U;
    return true;
}

static void RefreshRxDmaPosition(void)
{
    uint16_t write_index;
    uint32_t new_bytes;

    write_index = (uint16_t)(BSP_UART_RX_DMA_CAPACITY -
                             __HAL_DMA_GET_COUNTER(huart1.hdmarx));
    if (write_index >= BSP_UART_RX_DMA_CAPACITY)
    {
        write_index = 0U;
    }

    if (write_index >= s_rx_dma_last_write_index)
    {
        new_bytes = (uint32_t)(write_index - s_rx_dma_last_write_index);
    }
    else
    {
        new_bytes = (uint32_t)BSP_UART_RX_DMA_CAPACITY -
                    s_rx_dma_last_write_index + write_index;
    }
    s_rx_dma_last_write_index = write_index;

    if (new_bytes > ((uint32_t)BSP_UART_RX_DMA_CAPACITY - s_rx_dma_pending_count))
    {
        uint32_t lost = new_bytes -
                        ((uint32_t)BSP_UART_RX_DMA_CAPACITY - s_rx_dma_pending_count);
        s_rx_overflow_count += lost;
        s_rx_dma_read_index = (uint16_t)((s_rx_dma_read_index + lost) %
                                         BSP_UART_RX_DMA_CAPACITY);
        s_rx_dma_pending_count = BSP_UART_RX_DMA_CAPACITY;
    }
    else
    {
        s_rx_dma_pending_count += new_bytes;
    }
}

BspUartStatus_t BspUart_Init(void)
{
    if (huart1.Instance != USART1)
    {
        s_uart_ready = false;
        return BSP_UART_ERROR_NOT_READY;
    }

    s_rx_overflow_count = 0U;
    s_rx_error_count = 0U;
    s_rx_parity_error_count = 0U;
    s_rx_noise_error_count = 0U;
    s_rx_framing_error_count = 0U;
    s_rx_overrun_error_count = 0U;

    /* USART1 RX由循环DMA持续搬运，避免RTOS运行时逐字节中断造成接收溢出。 */
    if (!StartRxDma())
    {
        s_uart_ready = false;
        return BSP_UART_ERROR_HAL;
    }

    /* USART中断仅处理线路错误；普通接收字节不再进入RXNE中断。 */
    HAL_NVIC_SetPriority(USART1_IRQn, 4U, 0U);
    HAL_NVIC_EnableIRQ(USART1_IRQn);
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

    /* 长度上限检查保证转换为HAL长度类型时不会截断。 */
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

BspUartStatus_t BspUart_TryReadByte(uint8_t *byte, bool *received)
{
    if ((byte == NULL) || (received == NULL))
    {
        return BSP_UART_ERROR_INVALID_ARG;
    }
    *received = false;
    if (!s_uart_ready || (huart1.hdmarx == NULL))
    {
        return BSP_UART_ERROR_NOT_READY;
    }

    RefreshRxDmaPosition();
    if (s_rx_dma_pending_count != 0U)
    {
        *byte = s_rx_dma_storage[s_rx_dma_read_index];
        s_rx_dma_read_index = (uint16_t)((s_rx_dma_read_index + 1U) %
                                         BSP_UART_RX_DMA_CAPACITY);
        --s_rx_dma_pending_count;
        *received = true;
    }
    return BSP_UART_OK;
}

void BspUart_IrqHandler(void)
{
    HAL_UART_IRQHandler(&huart1);
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    uint32_t errors;

    if ((huart == NULL) || (huart->Instance != USART1))
    {
        return;
    }

    errors = huart->ErrorCode;
    ++s_rx_error_count;
    if ((errors & HAL_UART_ERROR_PE) != 0U)
    {
        ++s_rx_parity_error_count;
    }
    if ((errors & HAL_UART_ERROR_NE) != 0U)
    {
        ++s_rx_noise_error_count;
    }
    if ((errors & HAL_UART_ERROR_FE) != 0U)
    {
        ++s_rx_framing_error_count;
    }
    if ((errors & HAL_UART_ERROR_ORE) != 0U)
    {
        ++s_rx_overrun_error_count;
    }

    /* HAL在DMA接收错误后会中止通道；立即恢复循环接收，避免链路永久失效。 */
    if (!StartRxDma())
    {
        s_uart_ready = false;
    }
}

uint32_t BspUart_GetRxOverflowCount(void)
{
    return s_rx_overflow_count;
}

uint32_t BspUart_GetRxErrorCount(void)
{
    return s_rx_error_count;
}

bool BspUart_GetRxErrorStats(BspUartRxErrorStats_t *stats)
{
    if (stats == NULL)
    {
        return false;
    }
    stats->parity_count = s_rx_parity_error_count;
    stats->noise_count = s_rx_noise_error_count;
    stats->framing_count = s_rx_framing_error_count;
    stats->overrun_count = s_rx_overrun_error_count;
    return true;
}
