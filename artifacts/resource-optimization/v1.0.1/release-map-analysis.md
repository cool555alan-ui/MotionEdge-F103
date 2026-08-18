# Release map analysis

## Result

- Baseline: Flash 54,296 / 63,488 B; RAM 17,824 / 18,944 B.
- v1.0.1 candidate: Flash 54,296 / 63,488 B; RAM 17,824 / 18,944 B.
- Savings: 0 B Flash and 0 B RAM.
- Headroom: 9,192 B application Flash and 1,120 B RAM.
- Image end: `0x0800D41C`; reserved configuration starts at `0x0800F800`. Overlap: PASS.

## Sections

| Section | v1.0.0 | v1.0.1 | Delta |
|---|---:|---:|---:|
| `.text` | 52,012 B | 52,012 B | 0 B |
| `.rodata` | 1,896 B | 1,896 B | 0 B |
| `.data` | 104 B | 104 B | 0 B |
| `.bss` | 16,180 B | 16,180 B | 0 B |
| heap/stack reservation | 1,540 B | 1,540 B | 0 B |

## Effective build flags

Release compiles application, HAL, and FreeRTOS sources with `-Os -g0`, `-ffunction-sections`, `-fdata-sections`, and `-fstack-usage`. The linker uses nano specs and `--gc-sections`; LTO is off. The Debug-only `DEBUG` macro is absent.

```text
Compile: -Os -g0 -ffunction-sections -fdata-sections -fstack-usage
Link:    --specs=nano.specs -Wl,--gc-sections
LTO:     OFF
```

The v1.0.1 build-option change is scoped to Debug configuration, so Release is intentionally byte-for-byte unchanged in resource totals. Its 9,192 B Flash headroom is not the primary resource risk.

## Debug/Release difference

The v1.0.0 difference was 8,012 B: `.text` accounted for 7,872 B and `.rodata` for 140 B. It arose principally from Debug code generation and the `DEBUG` macro, not from absent section garbage collection. After size-optimizing stable HAL/FreeRTOS internals in Debug, the difference is 4,944 B while the application remains optimized for debugging.
