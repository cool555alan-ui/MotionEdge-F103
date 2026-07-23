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
    ../../Common/software_timer.c
    ../../App/app_status.c
    ../../Devices/mpu6050.c
    ../../Middleware/logger.c
    ../../Services/i2c_scanner.c
)

target_include_directories(firmware_host_tests PRIVATE
    .
    ../../App
    ../../Common
    ../../Devices
    ../../Middleware
    ../../Services
)

if(MSVC)
    target_compile_options(firmware_host_tests PRIVATE /W4)
else()
    target_compile_options(firmware_host_tests PRIVATE -Wall -Wextra -Wpedantic)
endif()

enable_testing()
add_test(NAME firmware_host_tests COMMAND firmware_host_tests)
