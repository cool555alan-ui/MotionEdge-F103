#ifndef CALIBRATION_SERVICE_H
#define CALIBRATION_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

#include "mpu6500.h"

typedef enum
{
    CALIBRATION_STATE_IDLE = 0,
    CALIBRATION_STATE_COLLECTING,
    CALIBRATION_STATE_COMPLETE,
    CALIBRATION_STATE_FAILED
} CalibrationState_t;

typedef struct
{
    int32_t gyro_bias_mdps_x;
    int32_t gyro_bias_mdps_y;
    int32_t gyro_bias_mdps_z;
    int32_t accel_bias_mg_x;
    int32_t accel_bias_mg_y;
    int32_t accel_bias_mg_z;
    uint32_t accepted_samples;
    uint32_t rejected_samples;
    bool valid;
} CalibrationResult_t;

/** 初始化RAM中的静止校准状态。 */
bool CalibrationService_Init(void);

/** 开始一次非阻塞静止校准。 */
bool CalibrationService_Start(void);

/** 处理一个缩放样本；函数不会等待后续样本。 */
void CalibrationService_ProcessSample(const Mpu6500ScaledSample_t *sample);

/** 返回当前校准状态。 */
CalibrationState_t CalibrationService_GetState(void);

/** 复制当前进度或最终校准结果。 */
bool CalibrationService_GetResult(CalibrationResult_t *result);

/** 清除进度和RAM校准结果。 */
void CalibrationService_Reset(void);

/** 将校准状态转换为非空字符串。 */
const char *CalibrationService_StateToString(CalibrationState_t state);

#endif /* CALIBRATION_SERVICE_H */
