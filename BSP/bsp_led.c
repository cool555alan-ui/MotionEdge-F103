#include "bsp_led.h"

#include "main.h"

BspLedStatus_t BspLed_Init(void)
{
    return BspLed_Off();
}

BspLedStatus_t BspLed_On(void)
{
    HAL_GPIO_WritePin(STATUS_LED_GPIO_Port, STATUS_LED_Pin, GPIO_PIN_RESET);
    return BSP_LED_OK;
}

BspLedStatus_t BspLed_Off(void)
{
    HAL_GPIO_WritePin(STATUS_LED_GPIO_Port, STATUS_LED_Pin, GPIO_PIN_SET);
    return BSP_LED_OK;
}

BspLedStatus_t BspLed_Toggle(void)
{
    HAL_GPIO_TogglePin(STATUS_LED_GPIO_Port, STATUS_LED_Pin);
    return BSP_LED_OK;
}
