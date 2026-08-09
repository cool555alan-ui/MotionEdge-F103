#include "tim.h"

TIM_HandleTypeDef htim3;
RCC_TypeDef g_test_rcc;
uint32_t g_test_pclk1_hz;
HAL_StatusTypeDef g_test_pwm_start_result;
HAL_StatusTypeDef g_test_pwm_stop_result;
unsigned int g_test_pwm_start_count;
unsigned int g_test_pwm_stop_count;

uint32_t HAL_RCC_GetPCLK1Freq(void) { return g_test_pclk1_hz; }

HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *timer, uint32_t channel)
{
    (void)timer; (void)channel; ++g_test_pwm_start_count;
    return g_test_pwm_start_result;
}

HAL_StatusTypeDef HAL_TIM_PWM_Stop(TIM_HandleTypeDef *timer, uint32_t channel)
{
    (void)timer; (void)channel; ++g_test_pwm_stop_count;
    return g_test_pwm_stop_result;
}
