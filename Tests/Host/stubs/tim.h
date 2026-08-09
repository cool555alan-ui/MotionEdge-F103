#ifndef HOST_TIM_STUB_H
#define HOST_TIM_STUB_H

#include <stdint.h>

typedef enum { HAL_OK = 0, HAL_ERROR = 1 } HAL_StatusTypeDef;

typedef struct
{
    uint32_t Prescaler;
    uint32_t Period;
} TIM_Base_InitTypeDef;

typedef struct
{
    void *Instance;
    TIM_Base_InitTypeDef Init;
    uint32_t compare;
} TIM_HandleTypeDef;

typedef struct { uint32_t CFGR; } RCC_TypeDef;

extern TIM_HandleTypeDef htim3;
extern RCC_TypeDef g_test_rcc;
extern uint32_t g_test_pclk1_hz;
extern HAL_StatusTypeDef g_test_pwm_start_result;
extern HAL_StatusTypeDef g_test_pwm_stop_result;
extern unsigned int g_test_pwm_start_count;
extern unsigned int g_test_pwm_stop_count;

#define RCC (&g_test_rcc)
#define RCC_CFGR_PPRE1 0x00000700U
#define RCC_HCLK_DIV1 0x00000000U
#define TIM3 ((void *)0x40000400U)
#define TIM_CHANNEL_1 0U

uint32_t HAL_RCC_GetPCLK1Freq(void);
HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *timer, uint32_t channel);
HAL_StatusTypeDef HAL_TIM_PWM_Stop(TIM_HandleTypeDef *timer, uint32_t channel);
#define __HAL_TIM_SET_COMPARE(timer, channel, value) \
    do { (void)(channel); (timer)->compare = (value); } while (0)

#endif /* HOST_TIM_STUB_H */
