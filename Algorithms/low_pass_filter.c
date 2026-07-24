#include "low_pass_filter.h"

#include <math.h>
#include <stddef.h>

bool LowPassFilter_Init(LowPassFilter_t *filter, float alpha)
{
    if ((filter == NULL) || !isfinite(alpha) || (alpha <= 0.0F) || (alpha > 1.0F))
    {
        return false;
    }

    filter->value = 0.0F;
    filter->alpha = alpha;
    filter->initialized = false;
    return true;
}

bool LowPassFilter_Reset(LowPassFilter_t *filter, float value)
{
    if ((filter == NULL) || !isfinite(value) || !isfinite(filter->alpha) ||
        (filter->alpha <= 0.0F) || (filter->alpha > 1.0F))
    {
        return false;
    }

    filter->value = value;
    filter->initialized = true;
    return true;
}

bool LowPassFilter_Update(LowPassFilter_t *filter, float input, float *output)
{
    if ((filter == NULL) || (output == NULL) || !isfinite(input) ||
        !isfinite(filter->alpha) || (filter->alpha <= 0.0F) ||
        (filter->alpha > 1.0F))
    {
        return false;
    }

    /* 首个样本直接建立初值，后续执行 y=alpha*x+(1-alpha)*y。 */
    if (!filter->initialized)
    {
        filter->value = input;
        filter->initialized = true;
    }
    else
    {
        filter->value =
            (filter->alpha * input) + ((1.0F - filter->alpha) * filter->value);
    }

    if (!isfinite(filter->value))
    {
        return false;
    }
    *output = filter->value;
    return true;
}
