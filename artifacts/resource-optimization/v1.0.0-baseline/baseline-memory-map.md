# MotionEdge-F103 v1.0.0 baseline memory map

- Commit: `16a2ccac9fb876b70058382c963a64e696be0c66`
- Toolchain: Arm GNU Toolchain 14.2.Rel1 / GCC 14.2.1
- Config reservation: 2048 B at `0x0800F800-0x0800FFFF` (excluded from application Flash totals).

## Section sizes

| Build | .text | .rodata | .data | .bss | heap/stack reserve | App Flash | RAM |
|---|---:|---:|---:|---:|---:|---:|---:|
| Debug | 59884 | 2036 | 104 | 16188 | 1540 | 62308 | 17832 |
| Release | 52012 | 1896 | 104 | 16180 | 1540 | 54296 | 17824 |

## Effective flags

- Debug compile flags: `-DDEBUG -DSTM32F103xB -DUSE_HAL_DRIVER -fdata-sections -ffunction-sections -fstack-usage -O0 -g3 -Og`
- Release compile flags: `-DSTM32F103xB -DUSE_HAL_DRIVER -fdata-sections -ffunction-sections -fstack-usage -Os -g0`
- Linker flags: `-mcpu=cortex-m3  -T "C:/STM32/MotionEdge-F103/STM32F103XX_FLASH.ld" --specs=nano.specs -Wl,-Map=MotionEdge-F103.map -Wl,--gc-sections -Wl,--print-memory-usage -Wl,--undefined=config_slots_reserve -Wl,--section-start=.config_slots=0x0800F800 -Wl,--defsym=__config_slot_a_start__=0x0800F800 -Wl,--defsym=__config_slot_a_end__=0x0800FC00 -Wl,--defsym=__config_slot_b_start__=0x0800FC00 -Wl,--defsym=__config_slot_b_end__=0x08010000`
- Effective Debug optimization is `-Og`: CMake emits `-O0` first and target options emit `-Og` later; GCC uses the last optimization option.
- Release uses `-Os`.
- Both builds use `-ffunction-sections`, `-fdata-sections`, and `-Wl,--gc-sections`.
- LTO is OFF in both builds.
- Debug defines `DEBUG`; Release does not.

## Debug versus Release

- Application Flash difference: 8012 B.
- `.text` accounts for 7872 B of the difference; `.rodata` accounts for 140 B.
- The dominant cause is `-Og` versus size-oriented `-Os`; debug DWARF sections do not consume MCU Flash because their VMA is zero.

## Top 20 object contributions

### Debug

| Object/source | Flash B | RAM B |
|---|---:|---:|
| `Middlewares/Third_Party/FreeRTOS/Source/tasks.c` | 5129 | 1280 |
| `Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_i2c.c` | 3396 | 0 |
| `App/app_main.c` | 3016 | 284 |
| `Services/command_service.c` | 2874 | 1 |
| `Middlewares/Third_Party/FreeRTOS/Source/queue.c` | 2654 | 64 |
| `Services/config_store.c` | 2434 | 100 |
| `Services/control_service.c` | 2340 | 236 |
| `Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_uart.c` | 2188 | 0 |
| `App/RTOS/rtos_tasks.c` | 2115 | 5056 |
| `Services/motion_service.c` | 1926 | 281 |
| `Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_tim.c` | 1702 | 0 |
| `Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_rcc.c` | 1686 | 0 |
| `Algorithms/pid_controller.c` | 1648 | 0 |
| `Middlewares/Third_Party/FreeRTOS/Source/CMSIS_RTOS_V2/cmsis_os2.c` | 1490 | 1724 |
| `Services/actuator_service.c` | 1424 | 57 |
| `Middlewares/Third_Party/FreeRTOS/Source/timers.c` | 1159 | 300 |
| `Services/communication_service.c` | 1086 | 909 |
| `Services/telemetry_service.c` | 1000 | 0 |
| `App/RTOS/rtos_objects.c` | 941 | 705 |
| `Algorithms/attitude_estimator.c` | 896 | 0 |

### Release

| Object/source | Flash B | RAM B |
|---|---:|---:|
| `Middlewares/Third_Party/FreeRTOS/Source/tasks.c` | 4737 | 1276 |
| `Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_i2c.c` | 2714 | 0 |
| `App/app_main.c` | 2639 | 284 |
| `Middlewares/Third_Party/FreeRTOS/Source/queue.c` | 2416 | 64 |
| `Services/control_service.c` | 2080 | 236 |
| `App/RTOS/rtos_tasks.c` | 1975 | 5056 |
| `Services/command_service.c` | 1888 | 1 |
| `Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_uart.c` | 1882 | 0 |
| `Services/config_store.c` | 1856 | 100 |
| `Services/motion_service.c` | 1584 | 281 |
| `Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_tim.c` | 1470 | 0 |
| `Algorithms/pid_controller.c` | 1444 | 0 |
| `Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_rcc.c` | 1354 | 0 |
| `Services/actuator_service.c` | 1342 | 57 |
| `Middlewares/Third_Party/FreeRTOS/Source/CMSIS_RTOS_V2/cmsis_os2.c` | 1202 | 1724 |
| `Middlewares/Third_Party/FreeRTOS/Source/timers.c` | 1021 | 300 |
| `Services/communication_service.c` | 990 | 909 |
| `Services/telemetry_service.c` | 864 | 0 |
| `C:/PROGRA~2/ARMGNU~1/14EFD8~1.2RE/bin/../lib/gcc/arm-none-eabi/14.2.1/thumb/v7-m/nofp/libg_nano.a(libc_a-nano-vfprintf_i.o)` | 838 | 0 |
| `Algorithms/attitude_estimator.c` | 810 | 0 |

## Notes

- Object contributions are parsed from linked map ranges, so discarded sections are excluded.
- Initialized `.data` bytes count toward both Flash load image and RAM.
- Linker-only RAM reservations are shown in the section totals but have no source object.
- Full Top-30 symbol and object tables are stored in the sibling CSV files.
