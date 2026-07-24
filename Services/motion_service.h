#ifndef MOTION_SERVICE_H
#define MOTION_SERVICE_H

#include <stdbool.h>
#include <stdint.h>

#include "attitude_estimator.h"
#include "calibration_service.h"
#include "mpu6050.h"

typedef enum
{
    MOTION_SAMPLE_FLAG_NONE = 0U,
    MOTION_SAMPLE_FLAG_STALE = 1U << 0,
    MOTION_SAMPLE_FLAG_ALL_ZERO = 1U << 1,
    MOTION_SAMPLE_FLAG_ACCEL_RANGE = 1U << 2,
    MOTION_SAMPLE_FLAG_GYRO_RANGE = 1U << 3,
    MOTION_SAMPLE_FLAG_SATURATED = 1U << 4,
    MOTION_SAMPLE_FLAG_BUS_ERROR = 1U << 5,
    MOTION_SAMPLE_FLAG_FIXED = 1U << 6
} MotionSampleFlag_t;

typedef enum
{
    MOTION_SERVICE_STATE_IDLE = 0,
    MOTION_SERVICE_STATE_CALIBRATING,
    MOTION_SERVICE_STATE_RUNNING,
    MOTION_SERVICE_STATE_DEGRADED
} MotionServiceState_t;

typedef struct
{
    uint32_t timestamp_ms;
    uint32_t sequence;
    uint32_t status_flags;
    Mpu6050ScaledSample_t raw_scaled;
    Mpu6050ScaledSample_t calibrated_sample;
    Mpu6050ScaledSample_t filtered;
    AttitudeOutput_t attitude;
    bool valid;
    bool calibrated;
} MotionFrame_t;

typedef struct
{
    uint32_t successful_samples;
    uint32_t invalid_samples;
    uint32_t dropped_samples;
    uint32_t recovery_count;
} MotionServiceStats_t;

/** 初始化数据质量、滤波和姿态状态。 */
bool MotionService_Init(uint32_t now_ms);

/** 处理SensorService提供的一个新序号样本。 */
void MotionService_RunOnce(uint32_t now_ms);

/** 启动一次非阻塞静止校准。 */
bool MotionService_StartCalibration(void);

/** 返回最近一个有效运动帧。 */
bool MotionService_GetLatestFrame(MotionFrame_t *frame);

/** 返回校准进度或最终结果。 */
bool MotionService_GetCalibration(CalibrationResult_t *result);

/** 返回当前运动管线状态。 */
MotionServiceState_t MotionService_GetState(void);

/** 返回状态的非空字符串。 */
const char *MotionService_StateToString(MotionServiceState_t state);

/** 返回成功、异常、丢弃和恢复统计。 */
bool MotionService_GetStats(MotionServiceStats_t *stats);

#endif /* MOTION_SERVICE_H */
