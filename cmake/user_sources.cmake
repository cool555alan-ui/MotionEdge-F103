target_sources(${CMAKE_PROJECT_NAME} PRIVATE
    ${CMAKE_SOURCE_DIR}/App/app_main.c
    ${CMAKE_SOURCE_DIR}/App/app_status.c
    ${CMAKE_SOURCE_DIR}/BSP/bsp_led.c
    ${CMAKE_SOURCE_DIR}/BSP/bsp_i2c.c
    ${CMAKE_SOURCE_DIR}/BSP/bsp_uart.c
    ${CMAKE_SOURCE_DIR}/Common/software_timer.c
    ${CMAKE_SOURCE_DIR}/Devices/mpu6050.c
    ${CMAKE_SOURCE_DIR}/Middleware/logger.c
    ${CMAKE_SOURCE_DIR}/Services/health_service.c
    ${CMAKE_SOURCE_DIR}/Services/i2c_scanner.c
)

target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    ${CMAKE_SOURCE_DIR}/App
    ${CMAKE_SOURCE_DIR}/BSP
    ${CMAKE_SOURCE_DIR}/Common
    ${CMAKE_SOURCE_DIR}/Devices
    ${CMAKE_SOURCE_DIR}/Middleware
    ${CMAKE_SOURCE_DIR}/Services
)
