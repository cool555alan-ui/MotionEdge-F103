#ifndef SENSOR_SERVICE_H
#define SENSOR_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

#include "mpu6050.h"
#include "software_timer.h"

typedef struct
{
    uint32_t timestamp_ms;
    uint32_t sequence;
    Mpu6050ScaledSample_t scaled;
    bool read_success;
} SensorSample_t;

/** 绑定已唤醒的MPU6050并建立100 Hz采样时间基准。 */
bool SensorService_Init(Mpu6050_t *device, uint32_t now_ms);

/** 到期时执行一次有界I²C采样，不在函数内部等待下一周期。 */
void SensorService_RunOnce(uint32_t now_ms);

/** 复制最近一次采样尝试，包括总线失败状态。 */
bool SensorService_GetLatestSample(SensorSample_t *sample);

#endif /* SENSOR_SERVICE_H */
