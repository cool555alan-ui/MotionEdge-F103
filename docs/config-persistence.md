# Configuration persistence

STM32F103C8 official 64 KiB Flash is split into a 62 KiB application region and two final 1 KiB pages: Slot A at `0x0800F800` and Slot B at `0x0800FC00`. A linker-owned NOLOAD reservation prevents application overlap.

Schema 1 stores fixed-width scaled integers. Each 54-byte record contains magic, schema/header/payload lengths, wrap-safe generation, payload, CRC16-CCITT-FALSE and a commit marker programmed last. Boot validates structure, schema, commit, CRC and every semantic field before applying the newest valid slot.

Runtime SET commands only set `dirty`. `config persist save` explicitly commits while actuator and PID control are disabled. Flash can only narrow the immutable 1450–1550 µs servo window and PID output cannot exceed ±10 µs. Arm, owner, enable state, PWM target, PID internal state, telemetry sessions and counters are never persisted.

`config persist factory-reset` requires explicit confirmation in motionctl and erases both slots only while the control path is safe. All boot, load and reset paths leave the actuator disarmed, owner NONE, PID disabled and PWM at 1500 µs.
