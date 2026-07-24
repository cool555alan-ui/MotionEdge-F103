cmake_minimum_required(VERSION 3.22)

project(MotionEdgeHostTests C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_executable(firmware_host_tests
    test_main.c
    test_software_timer.c
    test_app_status.c
    test_logger.c
    test_i2c_scanner.c
    test_mpu6050.c
    test_low_pass_filter.c
    test_attitude_estimator.c
    test_calibration_service.c
    test_motion_service.c
    test_csv_telemetry.c
    test_protocol.c
    ../../Algorithms/low_pass_filter.c
    ../../Algorithms/attitude_estimator.c
    ../../Common/software_timer.c
    ../../App/app_status.c
    ../../Devices/mpu6050.c
    ../../Middleware/logger.c
    ../../Middleware/csv_telemetry.c
    ../../Middleware/crc16.c
    ../../Middleware/byte_ring_buffer.c
    ../../Middleware/protocol_frame.c
    ../../Middleware/protocol_parser.c
    ../../Services/i2c_scanner.c
    ../../Services/health_service.c
    ../../Services/calibration_service.c
    ../../Services/motion_service.c
    ../../Services/sensor_service.c
    ../../Services/config_service.c
    ../../Services/command_service.c
    ../../Services/telemetry_service.c
)

target_include_directories(firmware_host_tests PRIVATE
    .
    ../../Algorithms
    ../../App
    ../../Common
    ../../Devices
    ../../Middleware
    ../../Services
)

target_compile_definitions(firmware_host_tests PRIVATE
    PROTOCOL_VECTOR_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../Fixtures/protocol_vectors.json"
)

if(MSVC)
    target_compile_options(firmware_host_tests PRIVATE /W4)
else()
    target_compile_options(firmware_host_tests PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(NOT MSVC)
    target_link_libraries(firmware_host_tests PRIVATE m)
endif()

enable_testing()
add_test(NAME firmware_host_tests COMMAND firmware_host_tests)
