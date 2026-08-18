# MotionEdge-F103 证据索引

本页只定位证据，不复制大型原始数据。指标解释与统一数值见 [`PROJECT_METRICS.md`](PROJECT_METRICS.md)，机器可读值见 [`project_metrics.json`](project_metrics.json)。历史 artifact 中的版本号、警告和限制必须与结果一起阅读。

## Phase 1：Firmware Foundation

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| 设计说明 | [`phase-01-firmware-foundation.md`](phase-01-firmware-foundation.md) | `2f12196` | PASS |
| Host C tests | `Tests/Host/` | `2f12196` | PASS |
| 代码入口 | `App/app_main.c`、`Common/software_timer.c`、`Middleware/logger.c` | `2f12196` | 代码事实 |

## Phase 2：I²C / MPU6500

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| 设计说明 | [`phase-02-i2c-mpu6500.md`](phase-02-i2c-mpu6500.md) | `dc683ed` | PASS |
| 综合实机摘要 | `artifacts/hardware-validation/hardware-validation-summary.json` | `738793a` / `v0.4-hardware-validated` | PASS |
| 实机报告 | `artifacts/hardware-validation/hardware-validation-report.md` | 同上 | PASS |
| 代码入口 | `BSP/bsp_i2c.c`、`Devices/mpu6500.c`、`Services/sensor_service.c` | 同上 | 代码事实 |

## Phase 3：Calibration / Attitude

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| 设计说明 | [`phase-03-calibration-attitude.md`](phase-03-calibration-attitude.md) | `f90f27c` | PASS |
| 综合实机摘要 | `artifacts/hardware-validation/hardware-validation-summary.json` | `738793a` / `v0.4-hardware-validated` | PASS |
| 代码入口 | `Services/calibration_service.c`、`Services/motion_service.c`、`Algorithms/attitude_estimator.c` | 同上 | 代码事实 |

## Phase 4：Binary Protocol

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| 规范 | [`protocol-specification.md`](protocol-specification.md) | `3dd5d5d` | PASS |
| 设计说明 | [`phase-04-device-protocol.md`](phase-04-device-protocol.md) | `3dd5d5d` | PASS |
| Golden vectors / parser tests | `Tests/Host/test_protocol.c`、`host/tests/test_protocol.py` | `3dd5d5d` 至 v1.0.1 | PASS |
| 代码入口 | `Middleware/protocol_frame.c`、`Middleware/protocol_parser.c`、`Services/command_service.c` | 同上 | 代码事实 |

## Phase 5：FreeRTOS

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| 设计说明 | [`phase-05-freertos-migration.md`](phase-05-freertos-migration.md)、[`rtos-task-design.md`](rtos-task-design.md) | `7314281` / `v0.5-freertos-validated` | PASS |
| Summary JSON | `artifacts/rtos-validation/rtos-validation-summary.json` | 同上 | PASS |
| 独立 600 s summary | `artifacts/rtos-validation/stability-soak-summary.json` | 同上 | PASS |
| CSV | `artifacts/rtos-validation/rtos-task-stats.csv` | 同上 | PASS |
| Report | `artifacts/rtos-validation/rtos-validation-report.md` | 同上 | PASS |

## Phase 6：Python Device Tools

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| 设计说明 | [`phase-06-python-device-tools.md`](phase-06-python-device-tools.md) | `d3cd713` / `v0.6-device-tools-validated` | PASS |
| Summary JSON | `artifacts/phase06/final-validation/phase06-validation-summary.json` | 同上 | PASS |
| Session metadata | `artifacts/phase06/final-validation/session-metadata.json` | 同上 | PASS |
| Metrics CSV | `artifacts/phase06/final-validation/report/metrics.csv` | 同上 | PASS |
| Report | `artifacts/phase06/final-validation/report/report.md` | 同上 | PASS |

## Phase 7：MQTT / Node-RED

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| 设计与方法 | [`phase-07-mqtt-gateway.md`](phase-07-mqtt-gateway.md)、[`phase-07-validation-method.md`](phase-07-validation-method.md) | `9a1cae1` / `v0.7-iot-gateway-validated` | PASS |
| Summary JSON | `artifacts/phase07/final-validation/phase07-validation-summary.json` | 同上 | PASS |
| Node-RED metrics | `artifacts/phase07/final-validation/node-red-metrics.json` | 同上 | PASS |
| Latency CSV | `artifacts/phase07/final-validation/latency-metrics.csv` | 同上 | PASS |
| Report | `artifacts/phase07/final-validation/phase07-validation-report.md` | 同上 | PASS |

关键边界：`2 ms` 是 Gateway → Node-RED 本地接收 P95；`216.58 ms` 是 PING command round-trip P95，两者不能混用。

## Phase 8：Attitude Characterization

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| Summary JSON | `artifacts/phase08/final-report/phase08-characterization-summary.json` | `ad4410f` / `v0.8-attitude-characterized` | PASS / `REFERENCE_LIMITED` |
| Report | `artifacts/phase08/final-report/phase08-characterization-report.md` | 同上 | PASS / `REFERENCE_LIMITED` |
| Static CSV | `artifacts/phase08/final-report/static-angle-results.csv` | 同上 | `REFERENCE_LIMITED` |
| Noise / drift CSV | `artifacts/phase08/final-report/noise-results.csv`、`drift-results.csv` | 同上 | PASS |
| Reference definition | `artifacts/phase08/reference/reference-setup.json` | 同上 | `REFERENCE_UNCERTAINTY_UNKNOWN` |
| Figures | `artifacts/phase08/final-report/figures/` | 同上 | 展示证据 |

关键边界：手机水平仪只作为工程比较参考，`0.352°/0.375°` 不是实验室绝对精度。

## Phase 9A：Safe PWM Actuator

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| 设计说明 | [`phase-09-actuator-control.md`](phase-09-actuator-control.md)、[`actuator-safety-model.md`](actuator-safety-model.md) | `03e9977` / `v0.9-actuator-validated` | PASS |
| Summary JSON | `artifacts/phase09/phase09-actuator-summary.json` | 同上 | PASS |
| Manual / safety CSV | `artifacts/phase09/manual-control-results.csv`、`artifacts/phase09/safety-validation.csv` | 同上 | PASS |
| Report | `artifacts/phase09/phase09-actuator-report.md` | 同上 | PASS |

## Phase 9B：PID-based Attitude-driven Servo Control

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| 设计说明 | [`pid-attitude-control.md`](pid-attitude-control.md) | `c00e184` / `v0.9.1-pid-attitude-validated` | PASS_WITH_WARNINGS |
| Summary JSON | `artifacts/phase09/pid-attitude/phase09b-pid-attitude-summary.json` | 同上 | PASS_WITH_WARNINGS |
| PID comparison CSV | `artifacts/phase09/pid-attitude/pid-config-comparison.csv` | 同上 | `HUMAN_INPUT_LIMITED` |
| Stability CSV | `artifacts/phase09/pid-attitude/stability-600s.csv` | 同上 | PASS_WITH_WARNINGS |
| Figures | `artifacts/phase09/pid-attitude/p-vs-pd.png`、`pwm-output.png`、`pid-terms.png` | 同上 | 展示证据 |
| Report | `artifacts/phase09/pid-attitude/phase09b-pid-attitude-report.md` | 同上 | PASS_WITH_WARNINGS |

关键边界：SG90 运动不反馈到 MPU6500；不存在可报告的机械外环超调、调节时间或稳态误差。

## Phase 10：Persistence / Final Acceptance / Release

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| Persistence report | `artifacts/phase10/persistence/phase10-persistence-report.md` | `16a2cca` / `v1.0.0` | PASS |
| Persistence summary | `artifacts/phase10/persistence/phase10-persistence-summary.json` | 同上 | PASS |
| Power-cycle CSV | `artifacts/phase10/persistence/power-cycle-results.csv` | 同上 | PASS |
| Fault-injection summary | `artifacts/phase10/persistence/fault-injection-summary.json` | 同上 | PASS（FakeFlash） |
| Final system summary | `artifacts/phase10/final-validation/system-600s-summary.json` | 同上 | PASS_WITH_WARNINGS，624.742 s |
| Release | `RELEASE_NOTES_v1.0.0.md` | `v1.0.0` | Published |

## v1.0.1：Resource Optimization

| 类型 | 位置 | Commit / Tag | 状态 |
|---|---|---|---|
| Baseline map/size | `artifacts/resource-optimization/v1.0.0-baseline/` | `41dfb83` | PASS |
| Optimization report | `artifacts/resource-optimization/v1.0.1/resource-optimization-report.md` | `11db478` | PASS |
| Summary JSON | `artifacts/resource-optimization/v1.0.1/resource-optimization-summary.json` | `5dcadaa` / `v1.0.1` | PASS |
| Before/after CSV | `artifacts/resource-optimization/v1.0.1/before-after-memory.csv` | 同上 | PASS |
| 123 s smoke | `artifacts/resource-optimization/v1.0.1/smoke-test-summary.json` | 同上 | PASS |
| Release | `RELEASE_NOTES_v1.0.1.md` | `v1.0.1` | Published |

## 快速追溯

- 姿态 MAE / R² / 噪声 / 漂移：Phase 8 summary。
- Task 频率 / Stack / Heap / fatal hooks：RTOS summary。
- PWM 安全与执行器状态：Phase 9A summary。
- PID 参数与 P/PD 统计：Phase 9B summary + comparison CSV。
- MQTT 消息、延迟、恢复：Phase 7 summary + latency CSV。
- 双槽 Flash 与真实掉电：Phase 10 persistence summary + power-cycle CSV。
- 最终 624.742 s 系统状态：Phase 10 final summary。
- v1.0.1 Flash/RAM：resource optimization summary。
