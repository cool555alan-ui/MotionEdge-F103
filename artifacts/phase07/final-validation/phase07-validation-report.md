# Phase 7 real-hardware validation

- Result: **PASS**
- Date: 2026-08-06T00:42:03.365100+08:00
- Device: STM32F103C8T6 + MPU6500, firmware 0.6.0
- Gateway: motionctl 0.7.0
- Serial: COM4, 115200 8N1
- Broker: 127.0.0.1:1884 (loopback, no TLS)
- Duration: 600.2 s

## Environment

- Validated firmware baseline commit: `d3cd713e75642f32fb2411f8a6ffaa8708b352f9`
- Paho MQTT: 2.1.0
- Mosquitto: 2.1.2
- Node-RED: 5.0.1; Node.js 24.15.0
- Build configuration: firmware Debug and Release unchanged from Phase 6

## Data

- Total motion / health: 5698 / 562
- Stable comparison gateway / Node-RED: 4934 / 4934
- Frequency: 10.0000 Hz; loss 0; duplicate 0; regression 0; gap 0
- Local gateway-to-Node-RED latency P50/P95/max: 1 / 2 / 3 ms
- PING success: 100/100; P50/P95/max: 201.89 / 216.5772 / 1308.6015 ms
- Broker recovery after 5 s outage: 2.798 s; LWT: True

## Acceptance matrix

- gateway_online: PASS
- device_online: PASS
- meta_state_retained: PASS
- telemetry_not_retained: PASS
- duration_600_seconds: PASS
- telemetry_frequency: PASS
- sequence_integrity: PASS
- json_schema_errors: PASS
- node_red_sequence: PASS
- device_crc_no_increase: PASS
- uart_overflow_no_increase: PASS
- motion_range: PASS
- ping_100_success: PASS
- command_p95_under_500_ms: PASS
- duplicate_not_reexecuted: PASS
- expired_rejected: PASS
- retained_rejected: PASS
- broker_recovery_under_10_s: PASS
- lwt_offline: PASS
- node_red_message_loss: PASS
- local_latency_p95: PASS
- stream_state_restored: PASS
- gateway_memory_bounded: PASS

The latency is a same-host local-broker observation, not public-internet performance.

## Supplemental real-MQTT motion check — attempt 1

- Result: **FAIL**
- Frames: 300
- Roll min/max/span: -0.03 / 0.04 / 0.07 deg
- Pitch min/max/span: -0.15 / -0.07 / 0.07999999999999999 deg
- Sequence continuous: True

## Supplemental real-MQTT motion check — final

- Result: **PASS**
- Frames: 300
- Roll min/max/span: -54.7 / 56.85 / 111.55000000000001 deg
- Pitch min/max/span: -27.41 / 29.98 / 57.39 deg
- Sequence continuous: True
