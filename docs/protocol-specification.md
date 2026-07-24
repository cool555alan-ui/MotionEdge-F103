# MotionEdge Binary Protocol v1

## Frame

All multibyte integers are little-endian.

| Field | Size | Meaning |
|---|---:|---|
| SOF1 | 1 | `0xA5` |
| SOF2 | 1 | `0x5A` |
| VERSION | 1 | `0x01` |
| TYPE | 1 | Message type |
| FLAGS | 1 | Reserved, currently zero |
| SEQUENCE | 2 | Request/response correlation |
| LENGTH | 2 | Payload bytes, 0 through 128 |
| PAYLOAD | N | Type-specific data |
| CRC16 | 2 | CRC in little-endian form |

CRC covers `VERSION` through the final payload byte. It does not cover SOF or
the CRC field. The algorithm is CRC16-CCITT-FALSE: polynomial `0x1021`,
initial value `0xFFFF`, RefIn false, RefOut false, XorOut `0x0000`.
`"123456789"` produces `0x29B1`.

The stream parser searches for `A5 5A`, retains a trailing `A5` across reads,
validates version and length before buffering the rest of a frame, and resumes
SOF search after version, length, or CRC failure. It accepts split frames,
adjacent frames, noise, and SOF bytes inside payloads.

## Message types and responses

Requests are `01 PING`, `02 GET_DEVICE_INFO`, `03 GET_STATUS`,
`04 GET_CONFIG`, `05 SET_CONFIG`, `06 START_CALIBRATION`,
`07 SET_STREAM_STATE`, and `08 GET_LATEST_MOTION`. Telemetry types are
`20 MOTION`, `21 HEALTH`, and reserved `22 EVENT`. All commands produce
`80 COMMAND_RESPONSE` with the request sequence.

The response payload is:

| Field | Size |
|---|---:|
| request_type | 1 |
| status_code | 1 |
| detail_code | 2 |
| data_length | 2 |
| data | N |

Status values 0 through 7 are `OK`, `INVALID_COMMAND`, `INVALID_LENGTH`,
`INVALID_VALUE`, `NOT_READY`, `BUSY`, `UNSUPPORTED`, and `INTERNAL_ERROR`.

Empty payload is required for PING, GET_DEVICE_INFO, GET_STATUS, GET_CONFIG,
START_CALIBRATION, and GET_LATEST_MOTION. SET_STREAM_STATE contains one byte
(`0` or `1`). SET_CONFIG contains the following exact 10-byte record:

| Field | Type | Valid range |
|---|---|---:|
| sensor_sample_period_ms | u16 | 5–100 |
| telemetry_period_ms | u16 | 20–5000 |
| low_pass_alpha_milli | u16 | 1–1000 |
| complementary_gyro_weight_milli | u16 | 500–999 |
| log_level | u8 | 0–4 (`DEBUG` through `NONE`) |
| telemetry_enabled | u8 | 0–1 |

Configuration is validated as a complete record, applied to RAM only, and is
not persisted to internal Flash.

## Telemetry payloads

Motion is exactly 45 bytes: `timestamp_ms u32`, `sequence u32`,
`status_flags u32`, `calibrated u8`, followed by signed i32 values
`ax_mg`, `ay_mg`, `az_mg`, `gx_mdps`, `gy_mdps`, `gz_mdps`,
`roll_cdeg`, and `pitch_cdeg`.

Health is exactly 30 bytes: `uptime_ms u32`, `app_state u8`,
`motion_state u8`, then u32 values `loop_count`, `i2c_error_count`,
`invalid_sample_count`, `protocol_rx_frames`, `protocol_crc_errors`, and
`rx_overflow_count`. Fields are serialized individually; C structure padding
is never transmitted.

## UART modes and host commands

Development mode emits text logs and CSV. Binary telemetry is disabled by
default. Enabling streaming enters protocol mode, in which USART1 emits only
binary frames; disabling returns to development mode.

From the repository root, set `PYTHONPATH=host` if the package is not installed:

```powershell
$env:PYTHONPATH = 'host'
python -m motionctl ports
python -m motionctl ping --port COM5
python -m motionctl info --port COM5
python -m motionctl status --port COM5
python -m motionctl config-get --port COM5
python -m motionctl config-set --port COM5 --telemetry-ms 100
python -m motionctl calibrate --port COM5
python -m motionctl stream --port COM5 --enable
python -m motionctl monitor --port COM5
python -m motionctl simulate-device
python -m motionctl self-test
```

The simulator is explicitly synthetic and does not represent physical sensor
or UART behavior.
