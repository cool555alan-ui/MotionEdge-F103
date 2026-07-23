#include "software_timer.h"

#include <stddef.h>

bool SoftwareTimer_Init(SoftwareTimer_t *timer, uint32_t now_ms, uint32_t period_ms)
{
    if ((timer == NULL) || (period_ms == 0U))
    {
        return false;
    }

    timer->last_run_ms = now_ms;
    timer->period_ms = period_ms;
    timer->initialized = true;
    return true;
}

bool SoftwareTimer_IsDue(SoftwareTimer_t *timer, uint32_t now_ms)
{
    uint32_t elapsed_ms;
    uint32_t elapsed_periods;

    if ((timer == NULL) || !timer->initialized || (timer->period_ms == 0U))
    {
        return false;
    }

    elapsed_ms = now_ms - timer->last_run_ms;
    if (elapsed_ms < timer->period_ms)
    {
        return false;
    }

    /*
     * Advance by whole periods instead of assigning now_ms. Unsigned subtraction
     * preserves correct behavior across uint32_t wraparound and limits drift.
     */
    elapsed_periods = elapsed_ms / timer->period_ms;
    timer->last_run_ms += elapsed_periods * timer->period_ms;
    return true;
}

void SoftwareTimer_Reset(SoftwareTimer_t *timer, uint32_t now_ms)
{
    if ((timer == NULL) || !timer->initialized)
    {
        return;
    }

    timer->last_run_ms = now_ms;
}
