# MQTT topic contract

All JSON objects use `schema_version: 1`. Device topics use `motionedge/v1/devices/{device_id}/`; gateway topics use `motionedge/v1/gateways/{gateway_id}/`.

| Suffix | QoS | Retained | Purpose |
|---|---:|:---:|---|
| `availability` | 1 | yes | device online/offline |
| `meta` | 1 | yes | immutable identity and versions |
| `state` | 1 | yes | latest application and sensor state |
| `telemetry/motion` | 0 | no | 10 Hz pose and IMU sample |
| `telemetry/health` | 0 | no | device and RTOS health |
| `events` | 1 | no | state transition or error |
| `command` | 1 | no | one whitelisted command model |
| `response` | 1 | no | correlated result |

Gateway `availability` and `state` are QoS 1 retained; gateway `metrics` is QoS 1 not retained. The LWT is retained `offline`. Commands carry a UUID, UTC issue/expiry times, and params. Retained side-effect commands and expired commands are rejected; duplicate UUIDs replay the cached response without touching the device.
