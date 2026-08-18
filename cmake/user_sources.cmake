target_sources(${CMAKE_PROJECT_NAME} PRIVATE
    ${CMAKE_SOURCE_DIR}/Algorithms/attitude_estimator.c
    ${CMAKE_SOURCE_DIR}/Algorithms/low_pass_filter.c
    ${CMAKE_SOURCE_DIR}/Algorithms/pid_controller.c
    ${CMAKE_SOURCE_DIR}/Components/servo_actuator.c
    ${CMAKE_SOURCE_DIR}/App/app_main.c
    ${CMAKE_SOURCE_DIR}/App/app_status.c
    ${CMAKE_SOURCE_DIR}/App/RTOS/app_rtos.c
    ${CMAKE_SOURCE_DIR}/App/RTOS/rtos_tasks.c
    ${CMAKE_SOURCE_DIR}/App/RTOS/rtos_objects.c
    ${CMAKE_SOURCE_DIR}/App/RTOS/rtos_monitor.c
    ${CMAKE_SOURCE_DIR}/BSP/bsp_led.c
    ${CMAKE_SOURCE_DIR}/BSP/bsp_i2c.c
    ${CMAKE_SOURCE_DIR}/BSP/bsp_uart.c
    ${CMAKE_SOURCE_DIR}/BSP/bsp_pwm.c
    ${CMAKE_SOURCE_DIR}/BSP/bsp_flash.c
    ${CMAKE_SOURCE_DIR}/BSP/config_flash_reserve.S
    ${CMAKE_SOURCE_DIR}/Common/software_timer.c
    ${CMAKE_SOURCE_DIR}/Devices/mpu6500.c
    ${CMAKE_SOURCE_DIR}/Middleware/logger.c
    ${CMAKE_SOURCE_DIR}/Middleware/csv_telemetry.c
    ${CMAKE_SOURCE_DIR}/Middleware/crc16.c
    ${CMAKE_SOURCE_DIR}/Middleware/byte_ring_buffer.c
    ${CMAKE_SOURCE_DIR}/Middleware/protocol_frame.c
    ${CMAKE_SOURCE_DIR}/Middleware/protocol_parser.c
    ${CMAKE_SOURCE_DIR}/Services/health_service.c
    ${CMAKE_SOURCE_DIR}/Services/i2c_scanner.c
    ${CMAKE_SOURCE_DIR}/Services/calibration_service.c
    ${CMAKE_SOURCE_DIR}/Services/motion_service.c
    ${CMAKE_SOURCE_DIR}/Services/sensor_service.c
    ${CMAKE_SOURCE_DIR}/Services/config_service.c
    ${CMAKE_SOURCE_DIR}/Services/config_store.c
    ${CMAKE_SOURCE_DIR}/Services/config_persistence.c
    ${CMAKE_SOURCE_DIR}/Services/telemetry_service.c
    ${CMAKE_SOURCE_DIR}/Services/command_service.c
    ${CMAKE_SOURCE_DIR}/Services/communication_service.c
    ${CMAKE_SOURCE_DIR}/Services/actuator_service.c
    ${CMAKE_SOURCE_DIR}/Services/control_service.c
)

target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    ${CMAKE_SOURCE_DIR}/Algorithms
    ${CMAKE_SOURCE_DIR}/App
    ${CMAKE_SOURCE_DIR}/App/RTOS
    ${CMAKE_SOURCE_DIR}/BSP
    ${CMAKE_SOURCE_DIR}/Common
    ${CMAKE_SOURCE_DIR}/Components
    ${CMAKE_SOURCE_DIR}/Devices
    ${CMAKE_SOURCE_DIR}/Middleware
    ${CMAKE_SOURCE_DIR}/Services
)

target_link_libraries(${CMAKE_PROJECT_NAME} m)

# CubeMX linker script保持原样；独立NOLOAD段保留官方64 KiB末尾两个1 KiB页。
target_link_options(${CMAKE_PROJECT_NAME} PRIVATE
    -Wl,--undefined=config_slots_reserve
    -Wl,--section-start=.config_slots=0x0800F800
    -Wl,--defsym=__config_slot_a_start__=0x0800F800
    -Wl,--defsym=__config_slot_a_end__=0x0800FC00
    -Wl,--defsym=__config_slot_b_start__=0x0800FC00
    -Wl,--defsym=__config_slot_b_end__=0x08010000
)
