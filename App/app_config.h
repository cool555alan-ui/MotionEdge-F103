#ifndef APP_CONFIG_H
#define APP_CONFIG_H

/* LED心跳周期，单位ms。 */
#define APP_HEARTBEAT_PERIOD_MS 500U
/* 健康与校准进度报告周期，单位ms。 */
#define APP_HEALTH_REPORT_PERIOD_MS 1000U
/* MPU6500采样周期，10 ms对应100 Hz。 */
#define APP_SENSOR_SAMPLE_PERIOD_MS 10U
/* 静止校准需要接受的样本数。 */
#define APP_CALIBRATION_SAMPLE_COUNT 500U
/* 静止判定允许的单轴最大角速度，单位mdps。 */
#define APP_CALIBRATION_MAX_GYRO_MDPS 5000
/* 静止判定允许的1 g模长误差，单位mg。 */
#define APP_CALIBRATION_ACCEL_TOLERANCE_MG 150
/* 进入或退出降级状态所需的连续样本数。 */
#define APP_SENSOR_MAX_CONSECUTIVE_INVALID 5U
/* CSV姿态遥测最小周期，单位ms。 */
#define APP_ATTITUDE_REPORT_PERIOD_MS 100U
/* 互补滤波陀螺仪权重，千分比。 */
#define APP_COMPLEMENTARY_GYRO_WEIGHT_MILLI 980U
/* 一阶低通滤波alpha，千分比。 */
#define APP_LOW_PASS_ALPHA_MILLI 200U
/* 运行时配置的默认日志级别，对应LOG_LEVEL_INFO。 */
#define APP_DEFAULT_LOG_LEVEL 1U
/* 二进制遥测默认关闭，避免与开发日志和CSV混流。 */
#define APP_DEFAULT_TELEMETRY_ENABLED 0U
/* 校准失败前允许累计拒绝的样本数。 */
#define APP_CALIBRATION_MAX_REJECTED_SAMPLES 2000U
/* 判定传感器输出长期固定所需的连续次数。 */
#define APP_SENSOR_FIXED_SAMPLE_LIMIT 50U
/* UART阻塞发送的有限超时，单位ms。 */
#define APP_UART_TIMEOUT_MS 20U
/* 单个I2C地址探测超时，单位ms。 */
#define APP_I2C_PROBE_TIMEOUT_MS 2U
/* I2C寄存器读写超时，单位ms。 */
#define APP_I2C_TRANSFER_TIMEOUT_MS 10U
/* 首次全地址扫描失败后的总线恢复与重试次数。 */
#define APP_I2C_SCAN_MAX_RETRIES 2U
/* 运行期间传感器掉线后的总线与器件重试间隔，避免故障时高频阻塞任务。 */
#define APP_SENSOR_RECOVERY_PERIOD_MS 1000U

/* CSV行缓冲区容量，包含字符串结束符。 */
#define APP_CSV_BUFFER_SIZE 192U

/* Fixed logger buffer capacity, including the terminating null character. */
#define APP_LOG_BUFFER_SIZE 192U

/* HAL system tick frequency in hertz. */
#define APP_FIRMWARE_TICK_HZ 1000U

#endif /* APP_CONFIG_H */
