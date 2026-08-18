# Debug map analysis

## Result

- Baseline: Flash 62,308 / 63,488 B; RAM 17,832 / 18,944 B.
- v1.0.1 candidate: Flash 59,240 / 63,488 B; RAM 17,824 / 18,944 B.
- Savings: 3,068 B Flash and 8 B RAM.
- Headroom: 4,248 B application Flash and 1,120 B RAM.
- Image end: `0x0800E76C`; reserved configuration starts at `0x0800F800`. Overlap: PASS.

## Sections

| Section | v1.0.0 | v1.0.1 | Delta |
|---|---:|---:|---:|
| `.text` | 59,884 B | 56,824 B | -3,060 B |
| `.rodata` | 2,036 B | 2,028 B | -8 B |
| `.data` | 104 B | 104 B | 0 B |
| `.bss` | 16,188 B | 16,180 B | -8 B |
| heap/stack reservation | 1,540 B | 1,540 B | 0 B |

## Effective build flags

The generated command line contains the toolchain default `-O0` before the target-specific option. GCC applies the last optimization option, so application sources are effectively `-Og`; STM32 HAL and FreeRTOS sources are effectively `-Os`. All targets retain `-g3`, `-ffunction-sections`, `-fdata-sections`, and `-fstack-usage`. The linker uses `--gc-sections`; LTO is off. The `DEBUG` macro is defined only for Debug.

Representative effective endings:

```text
Application: -O0 -g3 -std=gnu11 -Og
HAL:         -O0 -g3 -std=gnu11 -Os
FreeRTOS:    -O0 -g3 -std=gnu11 -Os
Link:        --specs=nano.specs -Wl,--gc-sections
LTO:         OFF
```

Debug information remains usable: `.debug_info` and `.debug_line` exist, and `addr2line` resolves both an HAL symbol and a FreeRTOS symbol to their source lines.

## Main contributors and decision

Before optimization, large object contributions included FreeRTOS `tasks.c` (5,129 B), HAL I2C (3,396 B), `app_main` (3,016 B), `command_service` (2,874 B), FreeRTOS queue (2,654 B), `config_store` (2,434 B), `control_service` (2,340 B), HAL UART (2,188 B), `rtos_tasks` (2,115 B), and `motion_service` (1,926 B). This supported optimizing stable runtime implementation code while leaving application code at `-Og`.

The linked nano-formatting path contains integer `snprintf`/`vsnprintf` support but no float formatting, `_dtoa`, or scanf family. Replacing it would affect diagnostic and CSV formatting and was rejected after the Flash target was exceeded. `.data` is only 104 B, so there is no meaningful misplaced mutable table. Task stacks, queues, heap, protocol buffers, control timing, and the UART path were not changed.
