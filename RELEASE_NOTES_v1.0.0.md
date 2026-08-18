# MotionEdge-F103 v1.0.0

MotionEdge-F103 combines STM32F103/MPU6500 attitude sensing, four FreeRTOS tasks, a binary serial protocol, Python gateway, local MQTT/Node-RED monitoring, safe SG90 PWM and 100 Hz PID-based attitude-driven servo control. Version 1.0 adds atomic dual-slot configuration persistence, factory reset, CI, resource gates and signed-by-hash release artifacts.

Hardware requires STM32F103C8T6, MPU6500, ST-LINK, CH340-compatible USB-TTL and an independently powered 5 V SG90 with common ground. Follow `QUICKSTART.md` and keep the servo path clear before Arm.

Validated safety boundaries are SG90 PWM 1450–1550 µs and PID output ±10 µs. Boot never restores Arm, owner or PID Enable. Sensor loss, stale motion, App Fault and ESTOP force the actuator safe.

Known limitations:

- Only one MPU6500 is used. PID drives the servo from hand-held attitude; it is not an external mechanical attitude closed loop.
- Phase 8 absolute accuracy uses an iPhone level and is `REFERENCE_LIMITED`.
- PWM electrical jitter is `NOT_TESTED`; servo overcurrent telemetry is `NOT_AVAILABLE`.
- The default local broker prototype has no TLS and must not be exposed publicly.
