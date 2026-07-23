#ifndef BSP_LED_H
#define BSP_LED_H

typedef enum
{
    BSP_LED_OK = 0,
    BSP_LED_ERROR
} BspLedStatus_t;

BspLedStatus_t BspLed_Init(void);
BspLedStatus_t BspLed_On(void);
BspLedStatus_t BspLed_Off(void);
BspLedStatus_t BspLed_Toggle(void);

#endif /* BSP_LED_H */
