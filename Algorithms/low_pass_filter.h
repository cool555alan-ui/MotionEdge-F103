#ifndef LOW_PASS_FILTER_H
#define LOW_PASS_FILTER_H

#include <stdbool.h>

typedef struct
{
    float value;
    float alpha;
    bool initialized;
} LowPassFilter_t;

/** 使用0到1之间的平滑系数初始化一阶低通滤波器。 */
bool LowPassFilter_Init(LowPassFilter_t *filter, float alpha);

/** 将滤波器状态复位到指定的有限值。 */
bool LowPassFilter_Reset(LowPassFilter_t *filter, float value);

/** 输入一个有限样本并返回最新滤波结果。 */
bool LowPassFilter_Update(LowPassFilter_t *filter, float input, float *output);

#endif /* LOW_PASS_FILTER_H */
