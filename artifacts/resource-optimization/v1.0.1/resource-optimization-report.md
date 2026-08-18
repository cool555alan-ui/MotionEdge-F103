# MotionEdge-F103 v1.0.1 resource optimization report

## Baseline

- Formal base: commit `16a2ccac9fb876b70058382c963a64e696be0c66`, tag `v1.0.0`.
- Debug: Flash 62,308 / 63,488 B; RAM 17,832 / 18,944 B.
- Release: Flash 54,296 / 63,488 B; RAM 17,824 / 18,944 B.
- Configuration reservation: 2,048 B at `0x0800F800-0x0800FFFF`.

## Resource analysis

The largest baseline Flash modules were FreeRTOS tasks, HAL I2C, application startup/orchestration, command handling, FreeRTOS queues, configuration storage, control, HAL UART, RTOS task glue, and motion processing. The largest RAM allocations remain the 3,072 B FreeRTOS heap, task stacks, scheduler ready lists, UART DMA buffer, protocol RX buffer, command queue, and diagnostic buffers.

Debug was already effectively `-Og`, Release was `-Os`, section splitting and linker garbage collection were already enabled, and LTO was off. The baseline Debug/Release Flash gap of 8,012 B was 7,872 B `.text` plus 140 B `.rodata`, chiefly from Debug code generation and the Debug macro.

## Applied optimization

| Change | Risk | Debug Flash saved | Release Flash saved | RAM saved | Decision |
|---|---|---:|---:|---:|---|
| Compile stable HAL and FreeRTOS implementation targets with Debug `-Os`; retain application `-Og` and all `-g3` debug information | LOW / Level A | 3,068 B | 0 B | 8 B Debug | KEPT |

Section GC was already active. Formatter replacement, log/string changes, const changes, dead-code deletion, buffer resizing, stack/queue reduction, static-RAM sharing, and LTO were not applied because the target was already exceeded and additional changes had a worse evidence/risk ratio.

## Final resources

| Resource | Before | After | Saved |
|---|---:|---:|---:|
| Debug Flash | 62,308 B | 59,240 B | 3,068 B |
| Release Flash | 54,296 B | 54,296 B | 0 B |
| Debug RAM | 17,832 B | 17,824 B | 8 B |
| Release RAM | 17,824 B | 17,824 B | 0 B |

- Debug remaining: 4,248 B Flash, 1,120 B RAM.
- Release remaining: 9,192 B Flash, 1,120 B RAM.
- Debug Flash headroom improved by 3,068 B and exceeds the 3,072 B target.
- Debug image end `0x0800E76C`; Release image end `0x0800D41C`; Flash overlap PASS.

## Behavior compatibility

- Binary Protocol v1 unchanged.
- Configuration Schema 1 and dual-slot Flash layout unchanged.
- MQTT topics, payloads, QoS, retained behavior, request IDs, duplicate rejection, and expiry rejection unchanged.
- PID parameters, Pitch axis, limits, deadband, derivative filtering, and update behavior unchanged.
- PWM safety window remains 1450/1500/1550 µs.
- Sensor, communication, telemetry, and health task frequencies unchanged.
- Hardware and wiring unchanged.

The product description remains PID-based attitude-driven servo control: MPU6500 attitude sensing feeds control computation, and the servo moves oppositely to demonstrate the response. The servo does not move the sensor, so this is not an external mechanical attitude closed loop.

## Reliability review

Bounds, timeout wrap, nonfinite guards, Flash range use, PWM range, static lifetime, and local arrays were inspected. Existing guards were retained. No independently proven reliability defect justified a code change. UART HAL line-error, stack-overflow, and malloc-failure binary telemetry remain `NOT_AVAILABLE`; the protocol was not expanded.

## Validation status

Final-candidate Host C, Python, Debug/Release, Phase 10, release, packaging, and 120-second post-optimization hardware smoke results are recorded in `resource-optimization-summary.json` and `smoke-test-summary.json`. No Level C change was made; historical 600-second and 1,800-second tests are not rerun.

## Long tests deliberately not rerun

- Phase 5 600 s: NOT_RERUN.
- Phase 7 600 s: NOT_RERUN.
- Phase 8 600/1800 s: NOT_RERUN.
- Phase 9B 600 s: NOT_RERUN.
- Phase 10 624 s: NOT_RERUN.
