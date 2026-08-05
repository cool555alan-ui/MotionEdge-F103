# Phase 7 MQTT gateway

Phase 7 adds a Windows edge gateway around the existing Phase 6 `DeviceClient`. The firmware protocol, CRC parser, serial transport, STM32 tasks, sampling rate, and attitude algorithm are unchanged. Firmware stays at 0.6.0; the Python gateway is 0.7.0.

The gateway has one serial owner and Paho's bounded network loop. MQTT callbacks only place validated bytes in a fixed 16-entry command queue. Telemetry is never accumulated while the broker is offline. Command results use a 128-entry, 600-second TTL cache keyed by UUID so QoS 1 duplicates do not repeat side effects.

Serial recovery uses bounded exponential backoff with jitter. Paho performs bounded reconnect delay, re-subscribes to the command topic, and republishes online/meta/state after recovery. Read-only commands inherit safe retries; configuration, calibration, and stream changes do not retry blindly.

Start locally:

```powershell
.\tools\start-phase07-broker.ps1
.\tools\start-phase07-node-red.ps1
.\tools\import-node-red-phase07.ps1
python -m motionctl gateway run --config .\config\motionedge-gateway.toml
```

The broker listens only on `127.0.0.1:1884`. TLS is not enabled and this setup is not suitable for a public network or production deployment. Username/password configuration is supported; secrets are read from an environment variable and are never committed.
