#include "bsp_uart.h"

#include <stdint.h>

#include "app_config.h"
#include "usart.h"

static bool s_uart_ready = false;
#define BSP_UART_RX_CAPACITY 64U
static uint8_t s_rx_storage[BSP_UART_RX_CAPACITY];
static volatile uint16_t s_rx_head;
static volatile uint16_t s_rx_tail;
static volatile uint32_t s_rx_overflow_count;
static volatile uint32_t s_rx_error_count;
static uint8_t s_rx_byte;

static void StartReceiveInterrupt(void)
{
    HAL_StatusTypeDef status = HAL_UART_Receive_IT(&huart1, &s_rx_byte, 1U);

    if ((status != HAL_OK) && (huart1.RxState != HAL_UART_STATE_BUSY_RX))
    {
        s_uart_ready = false;
    }
}

BspUartStatus_t BspUart_Init(void)
{
    if (huart1.Instance != USART1)
    {
        s_uart_ready = false;
        return BSP_UART_ERROR_NOT_READY;
    }

    s_rx_head = 0U;
    s_rx_tail = 0U;
    s_rx_overflow_count = 0U;
    s_rx_error_count = 0U;
    s_uart_ready = true;
    /* 接收ISR不调用RTOS API，优先级4可避免被FreeRTOS临界区屏蔽而产生ORE。 */
    HAL_NVIC_SetPriority(USART1_IRQn, 4U, 0U);
    HAL_NVIC_EnableIRQ(USART1_IRQn);
    StartReceiveInterrupt();
    if (!s_uart_ready)
    {
        return BSP_UART_ERROR_HAL;
    }
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

BspUartStatus_t BspUart_TryReadByte(uint8_t *byte, bool *received)
{
    uint16_t tail;

    if ((byte == NULL) || (received == NULL))
    {
        return BSP_UART_ERROR_INVALID_ARG;
    }
    *received = false;
    if (!s_uart_ready)
    {
        return BSP_UART_ERROR_NOT_READY;
    }
    tail = s_rx_tail;
    if (tail != s_rx_head)
    {
        *byte = s_rx_storage[tail];
        s_rx_tail = (uint16_t)((tail + 1U) % BSP_UART_RX_CAPACITY);
        *received = true;
    }
    return BSP_UART_OK;
}

void BspUart_IrqHandler(void)
{
    HAL_UART_IRQHandler(&huart1);
}

uint32_t BspUart_GetRxOverflowCount(void)
{
    return s_rx_overflow_count;
}

uint32_t BspUart_GetRxErrorCount(void)
{
    return s_rx_error_count;
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if ((huart != NULL) && (huart->Instance == USART1))
    {
        uint16_t next = (uint16_t)((s_rx_head + 1U) % BSP_UART_RX_CAPACITY);
        if (next == s_rx_tail)
        {
            ++s_rx_overflow_count;
        }
        else
        {
            s_rx_storage[s_rx_head] = s_rx_byte;
            s_rx_head = next;
        }
        StartReceiveInterrupt();
    }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    if ((huart != NULL) && (huart->Instance == USART1))
    {
        ++s_rx_error_count;
        /*
         * HAL对噪声/帧错误保持当前中断接收为BUSY，仅ORE会结束接收。
         * 只有接收已经回到READY时才重新挂载，避免把合法HAL_BUSY误判为永久故障。
         */
        /* F1通过依次读取SR和DR清除PE/FE/NE/ORE，避免错误中断反复进入。 */
        __HAL_UART_CLEAR_PEFLAG(huart);
        /* ORE属于阻塞错误，HAL已结束接收；FE/NE保持BUSY时无需中断当前接收。 */
        if (huart->RxState == HAL_UART_STATE_READY)
        {
            StartReceiveInterrupt();
        }
    }
}
