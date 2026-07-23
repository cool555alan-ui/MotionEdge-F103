#ifndef APP_CONFIG_H
#define APP_CONFIG_H

/* Application timing values are expressed in milliseconds. */
#define APP_HEARTBEAT_PERIOD_MS 500U
#define APP_HEALTH_REPORT_PERIOD_MS 1000U
#define APP_SENSOR_READ_PERIOD_MS 100U
#define APP_UART_TIMEOUT_MS 20U
#define APP_I2C_PROBE_TIMEOUT_MS 2U
#define APP_I2C_TRANSFER_TIMEOUT_MS 10U

/* Fixed logger buffer capacity, including the terminating null character. */
#define APP_LOG_BUFFER_SIZE 192U

/* HAL system tick frequency in hertz. */
#define APP_FIRMWARE_TICK_HZ 1000U

#endif /* APP_CONFIG_H */
