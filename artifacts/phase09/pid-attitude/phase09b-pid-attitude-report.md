# Phase 9B PID Attitude Control Hardware Validation

- Status: **PASS_WITH_WARNINGS**
- Date: 2026-08-09T22:00:31+08:00
- Commit: `03e99774f2e707c5c91fc97e703b8a1360995a9c` (validation worktree is not committed yet)
- Firmware/Gateway: 0.9.1 / 0.9.1

## Final configuration

Pitch, Normal, Kp=1.0 us/deg, Ki=0, Kd=0.05 us/(deg/s), deadband=1.0 deg, derivative alpha=0.2, integral disabled. PID output is a PWM offset limited to +/-10 us and still passes through ActuatorService's absolute 1450..1550 us clamp.

## Real hardware results

- Roll interaction: -7.70..5.42 deg, PWM 1492..1505 us, correlation 0.972.
- Pitch interaction: -45.15..45.61 deg, PWM 1490..1510 us, 3 reversals.
- Reverse mapping: relative/PWM correlation -0.996.
- Continuous run: 5976 frames / 599.86 s, PWM 1490..1503 us, faults 0, final Disabled/ESTOP.
- RTOS stack remaining: 384/568/200/456 B; heap 3064/2440 B; stack overflow and malloc failure 0.
- Broker-down and gateway-exit local-control tests: PASS. Node-RED quick regression: 52 frames, all parser/sequence checks 0, P95 1 ms.

## Safety

Arm, Disarm, ESTOP, Sensor offline, Motion stale, App Fault and PWM clamp all passed on real hardware. App Fault and Motion stale used volatile RAM injection at ELF-map addresses and were followed by reset; Flash and Option Bytes were not changed.

## Warnings

- The continuous 360-480 s stage did not contain visible Pitch movement; independent Pitch hardware evidence covers both directions.
- SensorTask deadline miss is a cumulative value of 19 since reset; no start snapshot exists, so its delta is NOT_TESTED.
- PWM electrical jitter is NOT_TESTED. The iPhone reference is REFERENCE_LIMITED.

## Control Interpretation and Limitations

1. The system has one MPU6500 and it measures user-held input attitude.
2. SG90 motion does not feed back into that MPU6500, so no external mechanical attitude loop exists.
3. The PID genuinely runs on STM32 at 100 Hz and changes real SG90 PWM; SG90 has its own internal position loop.
4. This is PID-based attitude-driven servo control. External plant settling time, overshoot and steady-state control error are NOT_APPLICABLE.

本阶段实现了基于单IMU姿态输入的PID舵机控制，PID在STM32端100 Hz真实运行；由于舵机运动不反馈至同一MPU6500，因此不将其描述为外部姿态闭环控制。
