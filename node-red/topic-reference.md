# Topic reference

设备前缀为`motionedge/v1/devices/{device_id}/`，包含`availability`、`meta`、`state`、
`telemetry/motion`、`telemetry/health`、`events`、`command`和`response`。网关前缀为
`motionedge/v1/gateways/{gateway_id}/`，包含`availability`、`state`和`metrics`。

availability/meta/state使用QoS 1且retained；motion/health默认QoS 0且不retained；command和
response使用QoS 1且不retained。
