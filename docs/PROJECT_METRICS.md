# MotionEdge-F103 项目指标事实源

本文与机器可读的 [`project_metrics.json`](project_metrics.json) 是 README、复试讲稿、Demo、简历和技术报告引用核心数字的唯一事实源。所有结果均来自仓库现有源码或 `artifacts/`；P2 未重跑硬件实验。

## 使用边界

- 项目定义：基于 STM32 的姿态感知与物联网控制平台。
- 控制定义：姿态感知 → PID 控制计算 → 执行器输出控制链，即 `PID-based attitude-driven servo control`。
- MPU6500 测量手持板姿态；SG90 不会反向改变该 MPU6500 姿态，因此不是外部机械姿态反馈闭环或自平衡系统。
- Phase 8 的手机水平仪参考不具备已知测量不确定度，相关 MAE、拟合与重复性均为 `REFERENCE_LIMITED`，不能称为绝对精度。
- `54.4%` 仅表示两组人工输入实验之间的 PWM 输出标准差下降，不能表述为超调、机械抖动或总体控制性能下降。

## A. Hardware

| 指标 | 值 | Evidence | Phase / 类型 | 状态与边界 |
|---|---:|---|---|---|
| MCU | STM32F103C8T6 | `artifacts/phase10/persistence/phase10-persistence-summary.json` | Phase 10 / 实机识别 | PASS，64 KiB Flash |
| IMU | MPU6500，I²C `0x68`，WHO_AM_I `0x70` | `artifacts/rtos-validation/rtos-validation-summary.json` | Phase 5 / 实机识别 | PASS，单六轴 IMU |
| Servo | SG90 | `artifacts/phase09/phase09-actuator-summary.json` | Phase 9A / 实机 | PASS，无负载演示 |
| UART | USART1，115200 bit/s，8N1 | `artifacts/phase07/final-validation/phase07-validation-summary.json` | Phase 7 / 实机 | PASS |
| PWM | TIM3_CH1 / PA6，50 Hz | `artifacts/phase09/phase09-actuator-summary.json` | Phase 9A / 实机 | PASS |
| 供电 | SG90 独立稳压 5 V，与 STM32 共地 | 同上 | Phase 9A / 安全配置 | 不从 MCU 电源轨直接带舵机 |

## B. Attitude

| 指标 | 值 | Evidence | Phase / 类型 | 状态与边界 |
|---|---:|---|---|---|
| 采样频率 | 100 Hz | `artifacts/phase08/final-report/phase08-characterization-summary.json` | Phase 8 / 实机配置 | PASS |
| 静态校准 | 500 samples | `App/app_config.h` | Phase 3 / 源码配置 | PASS |
| 低通系数 | 0.20 | Phase 8 summary | Phase 8 / 实测选型 | PASS |
| 互补滤波陀螺仪权重 | 0.98 | Phase 8 summary | Phase 8 / 实测选型 | PASS，加速度计权重 0.02 |
| Roll / Pitch MAE | 0.352° / 0.375° | Phase 8 summary | 静态手机水平仪比较 | `REFERENCE_LIMITED` |
| Roll / Pitch R² | 0.99888 / 0.99937 | Phase 8 summary | 静态线性拟合 | `REFERENCE_LIMITED` |
| Roll / Pitch 重复性标准差 | 0.245° / 0.408° | Phase 8 summary | 重复放置 | `REFERENCE_LIMITED`，实验部分完成 |
| Roll / Pitch 静态标准差 | 0.019° / 0.016° | Phase 8 summary | 600 s，6001 样本 | PASS |
| Roll / Pitch 30 min 漂移 | -0.0099° / -0.0307° | Phase 8 summary | 1800 s 静态记录 | PASS，工程表征 |

## C. FreeRTOS

| 指标 | 设计值 | 历史代表实测 | Evidence | 状态与边界 |
|---|---:|---:|---|---|
| SensorTask | 100 Hz | 100.003 Hz | `artifacts/rtos-validation/rtos-validation-summary.json` | PASS；采样、姿态、控制 |
| CommunicationTask | ~500 Hz | 500.012 Hz | 同上 | PASS |
| TelemetryTask | 10 Hz | 10.001 Hz | 同上 | PASS |
| HealthTask | 1 Hz | 1.000 Hz | 同上 | PASS |
| 独立稳定性记录 | — | 600 s | 同上 | PASS；不是工业寿命验证 |
| Stack Overflow / Malloc Failure | — | 0 / 0 | 同上 | PASS；仅代表该历史运行 |
| v1.0 最终系统验收 | — | 624.742 s | `artifacts/phase10/final-validation/system-600s-summary.json` | PASS_WITH_WARNINGS |
| 最终验收 deadline delta | — | Sensor 1，其余任务 0 | 同上 | 单次 miss 未导致 reset、fault、数据损坏或控制失败 |

历史实测小数用于说明对应运行中的调度表现，不暗示所有版本、每次运行都精确相同。

## D. PID / Actuator

| 指标 | 值 | Evidence | Phase / 类型 | 状态与边界 |
|---|---:|---|---|---|
| 本地控制频率 | 100 Hz | `artifacts/phase09/pid-attitude/phase09b-pid-attitude-summary.json` | Phase 9B / 实机 | SensorTask 内执行 |
| 最终轴 | Pitch | 同上 | Phase 9B / 配置 | Roll 可选 |
| Kp / Ki / Kd | 1.0 / 0 / 0.05 | 同上 | Phase 9B / 实测选型 | 完整 PID 实现，最终采用 PD 配置 |
| D filter alpha | 0.2 | 同上 | Phase 9B / 配置 | PASS |
| Deadband | 1.0° | 同上 | Phase 9B / 配置 | PASS |
| PID 输出限幅 | ±10 µs | 同上 | Phase 9B / 安全验证 | 相对 1500 µs |
| PWM 安全窗口 | 1450 / 1500 / 1550 µs | `artifacts/phase09/phase09-actuator-summary.json` | Phase 9A / 实机 | 绝对限幅/中心位 |
| P-only PWM 输出标准差 | 5.555 µs | `artifacts/phase09/pid-attitude/pid-config-comparison.csv` | Phase 9B / 人工输入 | `HUMAN_INPUT_LIMITED` |
| PD PWM 输出标准差 | 2.535 µs | 同上 | Phase 9B / 人工输入 | `HUMAN_INPUT_LIMITED` |
| PWM 输出标准差下降 | 54.4% | 同上 | `(5.555-2.535)/5.555` | 不能推广为机械抖动或总体性能 |

## E. IoT

| 指标 | 值 | Evidence | Phase / 类型 | 状态与边界 |
|---|---:|---|---|---|
| 稳定窗口 Gateway / Node-RED Motion | 4934 / 4934 | `artifacts/phase07/final-validation/phase07-validation-summary.json` | Phase 7 / 600 s 实机 | PASS，loss 0；不承诺永久零丢失 |
| Gateway → Node-RED 本地 P95 | 2 ms | `artifacts/phase07/final-validation/latency-metrics.csv` | Phase 7 / 本地接收延迟 | PASS |
| Broker recovery | 2.80 s | Phase 7 summary | Phase 7 / 中断恢复 | PASS，门限 10 s |
| PING command RTT P95 | 216.58 ms | Phase 7 summary | Phase 7 / 命令往返 | PASS，门限 500 ms；不是遥测延迟 |
| v1.0 Node-RED P95 / max | 1 ms / 2 ms | `artifacts/phase10/final-validation/system-600s-summary.json` | Phase 10 / 本地接收延迟 | PASS_WITH_WARNINGS |
| v1.0 Broker interruption | 27.068 s | 同上 | Phase 10 / 系统验收 | PASS，本地 PID 连续运行 |

## F. Persistence

| 指标 | 值 | Evidence | Phase / 类型 | 状态与边界 |
|---|---:|---|---|---|
| 双槽保留区 | 2048 B，`0x0800F800–0x0800FFFF` | `artifacts/phase10/persistence/phase10-persistence-summary.json` | Phase 10 / 布局+实机 | PASS，无应用重叠 |
| Record / Schema | 54 B / Schema 1 | 同上 | Phase 10 / 格式 | CRC16、generation、commit marker |
| Power Cycle / RAM-only discard / Slot switch / Factory Reset / Safe Boot | 全部 PASS | `artifacts/phase10/persistence/power-cycle-results.csv` | Phase 10 / 真实断电 | 断电至少 2 s |
| Fault Injection | PASS | `artifacts/phase10/persistence/fault-injection-summary.json` | Phase 10 / FakeFlash | 软件故障注入，不冒充物理注入 |
| 安全启动 | Control disabled；Actuator disarmed；Owner NONE；PID disabled；PWM 1500 µs | Phase 10 persistence summary | Phase 10 / 真实重启 | PASS |

## G. Resource

| 构建 | Flash | RAM | Evidence | 状态 |
|---|---:|---:|---|---|
| v1.0.0 Debug | 62308 B | 17832 B | `artifacts/resource-optimization/v1.0.0-baseline/` | PASS |
| v1.0.0 Release | 54296 B | 17824 B | 同上 | PASS |
| v1.0.1 Debug | 59240 B | 17824 B | `artifacts/resource-optimization/v1.0.1/resource-optimization-summary.json` | PASS |
| v1.0.1 Release | 54296 B | 17824 B | 同上 | PASS |

v1.0.1 Debug Flash 节省 3068 B，剩余 4248 B；RAM 剩余 1120 B。优化方式是 HAL/FreeRTOS 的 Debug 编译使用 `-Os`，应用代码保持 `-Og -g3`。没有缩减 Task Stack、Queue、协议 Buffer 或安全逻辑，也没有启用 LTO。

## 指标维护规则

1. 主展示材料不得自行重新计算或四舍五入另一套数字；需要新增指标时，先更新 JSON 和本页证据。
2. 历史 artifacts 保持原样；版本、工具和测试边界随指标一起引用。
3. 无法从现有 evidence 确认的数字直接删除，不为丰富 README 而补跑测试。
4. 使用 `python tools/check-doc-metrics.py` 检查主展示文档的一致性。
