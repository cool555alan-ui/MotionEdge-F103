# Node-RED monitoring page

The Phase 7 Flow uses only Node-RED core MQTT, Function, HTTP, WebSocket, and response nodes. No dashboard package is required or installed. Import with `tools/import-node-red-phase07.ps1`; it backs up existing Flows, replaces only the known Phase 7 IDs, and preserves unrelated user Flows.

The page at `http://127.0.0.1:1880/motionedge/` shows gateway/device availability, state, versions, roll, pitch, acceleration magnitude, telemetry frequency, a bounded 60-second chart, device/RTOS health, and gateway metrics. Unsupported protocol fields display `NOT_AVAILABLE`. UI history is capped at 300 points and rendering is limited independently of MQTT receive rate.

Commands are limited to PING, status/config reads, calibration, and stream start/stop. Each request has a UUID and expiry; calibration requires confirmation and side effects are disabled while offline. Automation reads `/motionedge/api/status` and `/motionedge/api/metrics`; no arbitrary command execution endpoint exists.
