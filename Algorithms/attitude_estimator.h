#ifndef ATTITUDE_ESTIMATOR_H
#define ATTITUDE_ESTIMATOR_H

#include <stdbool.h>
#include <stdint.h>

#include "mpu6050.h"

typedef struct
{
    float roll_deg;
    float pitch_deg;
    float accel_roll_deg;
    float accel_pitch_deg;
    float gyro_roll_deg;
    float gyro_pitch_deg;
    uint32_t last_timestamp_ms;
    float gyro_weight;
    bool initialized;
} AttitudeEstimator_t;

typedef struct
{
    int32_t roll_cdeg;
    int32_t pitch_cdeg;
    int32_t accel_roll_cdeg;
    int32_t accel_pitch_cdeg;
    bool valid;
} AttitudeOutput_t;

/** 初始化互补滤波姿态估计器。 */
bool AttitudeEstimator_Init(AttitudeEstimator_t *estimator);

/** 使用当前加速度方向重置Roll/Pitch和时间基准。 */
bool AttitudeEstimator_Reset(AttitudeEstimator_t *estimator,
                             const Mpu6050ScaledSample_t *sample,
                             uint32_t timestamp_ms);

/** 使用真实毫秒时间差更新Roll/Pitch，输出单位为0.01度。 */
bool AttitudeEstimator_Update(AttitudeEstimator_t *estimator,
                              const Mpu6050ScaledSample_t *sample,
                              uint32_t timestamp_ms,
                              AttitudeOutput_t *output);
/** 更新互补滤波陀螺仪权重，范围0.5至0.999。 */
bool AttitudeEstimator_SetGyroWeight(AttitudeEstimator_t *estimator,
                                    float gyro_weight);

#endif /* ATTITUDE_ESTIMATOR_H */
