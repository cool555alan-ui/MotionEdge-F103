#ifndef BSP_PWM_H
#define BSP_PWM_H

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    BSP_PWM_OK = 0,
    BSP_PWM_ERROR_INVALID_ARG,
    BSP_PWM_ERROR_NOT_READY,
    BSP_PWM_ERROR_HAL
} BspPwmStatus_t;

BspPwmStatus_t BspPwm_Init(void);
BspPwmStatus_t BspPwm_Start(void);
BspPwmStatus_t BspPwm_Stop(void);
BspPwmStatus_t BspPwm_SetPulseUs(uint16_t pulse_us);
uint16_t BspPwm_GetPulseUs(void);
bool BspPwm_IsRunning(void);

#endif /* BSP_PWM_H */
