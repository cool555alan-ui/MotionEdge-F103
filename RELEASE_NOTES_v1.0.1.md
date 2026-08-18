# MotionEdge-F103 v1.0.1

MotionEdge-F103 v1.0.1 is a resource-footprint and reliability maintenance release. It preserves the v1.0.0 feature set and external behavior while increasing Debug firmware Flash headroom.

Changes:

- Compile stable STM32 HAL and FreeRTOS runtime internals with `-Os` in Debug builds while retaining `-Og` for application code and debug symbols for all targets.
- Reduce Debug Flash usage from 62,308 bytes to 59,240 bytes, saving 3,068 bytes and increasing application Flash headroom from 1,180 bytes to 4,248 bytes.
- Keep Release firmware size unchanged at 54,296 bytes.
- Make release validation and packaging scripts derive release-note and artifact names from `VERSION`.

Compatibility:

- No new user-facing features.
- No binary protocol changes; configuration schema remains version 1.
- No PID parameter, control-frequency or PWM safety-boundary changes.
- No MQTT topic, payload or command-contract changes.
- No hardware or wiring changes.

Hardware requires STM32F103C8T6, MPU6500, ST-LINK, CH340-compatible USB-TTL and an independently powered 5 V SG90 with common ground. The MPU6500 senses hand-held attitude, and the servo moves in the opposing direction to demonstrate attitude perception and feedback behavior; the servo does not reposition the sensor and this is not an external mechanical attitude closed loop.

Validated safety boundaries remain SG90 PWM 1450–1550 µs and PID output ±10 µs. Boot never restores Arm, owner or PID Enable. Sensor loss, stale motion, App Fault and ESTOP force the actuator safe.

Known limitations:

- Only one MPU6500 is used; servo response demonstrates attitude-driven feedback rather than stabilizing the sensor platform.
- Phase 8 absolute accuracy uses an iPhone level and is `REFERENCE_LIMITED`.
- PWM electrical jitter is `NOT_TESTED`; servo overcurrent telemetry is `NOT_AVAILABLE`.
- The default local broker prototype has no TLS and must not be exposed publicly.
