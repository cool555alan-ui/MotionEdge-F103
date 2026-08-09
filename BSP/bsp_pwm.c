#include "bsp_pwm.h"

#include <stdint.h>

#include "tim.h"

static bool s_ready;
static bool s_running;
static uint16_t s_pulse_us;

static uint32_t BspPwm_GetTimerClockHz(void)
{
    uint32_t clock_hz = HAL_RCC_GetPCLK1Freq();

    /* STM32F1 的 APB1 分频大于 1 时，定时器时钟自动乘 2。 */
    if ((RCC->CFGR & RCC_CFGR_PPRE1) != RCC_HCLK_DIV1)
    {
        clock_hz *= 2U;
    }
    return clock_hz;
}

BspPwmStatus_t BspPwm_Init(void)
{
    uint32_t counter_hz;

    s_ready = false;
    s_running = false;
    s_pulse_us = 0U;
    if ((htim3.Instance != TIM3) || (htim3.Init.Period == 0U))
    {
        return BSP_PWM_ERROR_NOT_READY;
    }
    counter_hz = BspPwm_GetTimerClockHz() / (htim3.Init.Prescaler + 1U);
    if ((counter_hz == 0U) || (counter_hz > 10000000U))
    {
        return BSP_PWM_ERROR_NOT_READY;
    }
    s_ready = true;
    return BSP_PWM_OK;
}

BspPwmStatus_t BspPwm_Start(void)
{
    if (!s_ready)
    {
        return BSP_PWM_ERROR_NOT_READY;
    }
    if (s_running)
    {
        return BSP_PWM_OK;
    }
    if (HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_1) != HAL_OK)
    {
        return BSP_PWM_ERROR_HAL;
    }
    s_running = true;
    return BSP_PWM_OK;
}

BspPwmStatus_t BspPwm_Stop(void)
{
    if (!s_ready)
    {
        return BSP_PWM_ERROR_NOT_READY;
    }
    if (!s_running)
    {
        return BSP_PWM_OK;
    }
    if (HAL_TIM_PWM_Stop(&htim3, TIM_CHANNEL_1) != HAL_OK)
    {
        return BSP_PWM_ERROR_HAL;
    }
    s_running = false;
    return BSP_PWM_OK;
}

BspPwmStatus_t BspPwm_SetPulseUs(uint16_t pulse_us)
{
    uint32_t counter_hz;
    uint64_t ticks;

    if (!s_ready)
    {
        return BSP_PWM_ERROR_NOT_READY;
    }
    counter_hz = BspPwm_GetTimerClockHz() / (htim3.Init.Prescaler + 1U);
    ticks = ((uint64_t)pulse_us * counter_hz + 999999U) / 1000000U;
    if ((ticks > htim3.Init.Period) || (ticks > UINT32_MAX))
    {
        return BSP_PWM_ERROR_INVALID_ARG;
    }
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, (uint32_t)ticks);
    s_pulse_us = pulse_us;
    return BSP_PWM_OK;
}

uint16_t BspPwm_GetPulseUs(void)
{
    return s_pulse_us;
}

bool BspPwm_IsRunning(void)
{
    return s_running;
}
