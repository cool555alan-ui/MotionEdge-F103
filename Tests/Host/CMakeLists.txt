cmake_minimum_required(VERSION 3.22)

project(MotionEdgeHostTests C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_executable(phase1_host_tests
    test_main.c
    test_software_timer.c
    test_app_status.c
    test_logger.c
    ../../Common/software_timer.c
    ../../App/app_status.c
    ../../Middleware/logger.c
)

target_include_directories(phase1_host_tests PRIVATE
    .
    ../../App
    ../../Common
    ../../Middleware
)

if(MSVC)
    target_compile_options(phase1_host_tests PRIVATE /W4)
else()
    target_compile_options(phase1_host_tests PRIVATE -Wall -Wextra -Wpedantic)
endif()

enable_testing()
add_test(NAME phase1_host_tests COMMAND phase1_host_tests)
