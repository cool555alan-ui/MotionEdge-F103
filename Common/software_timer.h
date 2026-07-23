#ifndef SOFTWARE_TIMER_H
#define SOFTWARE_TIMER_H

#include <stdbool.h>
#include <stdint.h>

typedef struct
{
    uint32_t last_run_ms;
    uint32_t period_ms;
    bool initialized;
} SoftwareTimer_t;

bool SoftwareTimer_Init(SoftwareTimer_t *timer, uint32_t now_ms, uint32_t period_ms);
bool SoftwareTimer_IsDue(SoftwareTimer_t *timer, uint32_t now_ms);
void SoftwareTimer_Reset(SoftwareTimer_t *timer, uint32_t now_ms);

#endif /* SOFTWARE_TIMER_H */
