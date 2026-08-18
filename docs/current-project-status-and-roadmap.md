# MotionEdge-F103 当前状态与优化路线

更新时间：2026-08-17。本文基于仓库源码、验证脚本和 `artifacts/` 中的验收记录整理；它不把历史报告中的模拟、参考受限或未测试项表述为已完成能力。

## 1. 项目当前定义

当前硬件链路为：

`STM32F103C8T6 最小系统板 -> USART1/CH340 -> PC Python Gateway -> 本地 Mosquitto -> Node-RED Web 面板`

`MPU6500 (PB6/PB7 I2C1) -> SensorTask/姿态解算 -> 相对零位/反向映射/PID -> ActuatorService -> TIM3_CH1 PA6 -> SG90`

- MPU6500：地址 `0x68`，`WHO_AM_I=0x70`；已验证采集、静态校准、低通和 Roll/Pitch 互补滤波。
- 串口：USART1 PA9/PA10，115200 bps；使用 CRC16 二进制协议，DMA 环形接收。
- 舵机：SG90 信号接 PA6，TIM3_CH1、50 Hz、1 us 计数。须使用独立稳压 5 V 电源，且与 STM32 共地。
- 物联网：当前实现是本地 MQTT（默认 `127.0.0.1:1884`）和 Node-RED，不是公网云平台；MQTT 可下发控制/PID 配置并展示遥测。
- 波形：Node-RED 前端已有 60 秒 Roll/Pitch 曲线与控制曲线（相对角、PID 输出、P/D 项）。

## 2. 当前项目的控制定义与边界

当前目标是：MPU6500 感知用户手持面包板/最小系统板的 Roll 或 Pitch，相对于零位计算偏差，SG90 按配置的反向关系作出对应转动。PID 用于让输入偏差到 PWM 偏移的映射平滑、受限且可调。

推荐对外名称：**基于姿态感知的 PID 反向舵机跟随控制**（PID-based attitude-sensing inverse servo following）。

它突出“姿态感知 + 闭环算法”：传感器提供连续姿态反馈，PID 根据相对零位误差计算输出，且输出经死区、限幅、斜率和安全状态机约束。不过，舵机输出未反馈到该传感器，因此在严格控制理论中，它不是“机构姿态闭环”或自平衡平台，而是**带姿态反馈输入的反向舵机跟随控制**。报告或答辩中应主动说明这一边界；只有把传感器/编码器放到舵机带动机构上，才能额外宣称“机构姿态闭环”。

## 3. 已完成能力与证据

| 阶段 | 状态 | 已完成内容 |
| --- | --- | --- |
| 1：基础固件 | PASS | LED、日志、应用状态、软件定时器、交叉编译与主机 C 测试。 |
| 2：I2C/MPU6500 | PASS | I2C 扫描、唤醒、六轴读取；实机识别 `0x68/0x70`。 |
| 3：校准与姿态 | PASS | 500 样本校准、低通、Roll/Pitch、100 Hz 采样及 CSV 遥测。 |
| 4：设备协议 | PASS | CRC16 帧协议、运行时配置、串口命令与模拟器。 |
| 5：FreeRTOS | PASS | Sensor 100 Hz、Communication 500 Hz、Telemetry 10 Hz、Health 1 Hz；实机 600 秒稳定性已验收。 |
| 6：主机工具 | PASS | `motionctl` 诊断、采集、校准、报告、模拟器。 |
| 7：MQTT/Node-RED | PASS | 网关、主题契约、命令去重/过期拒绝、10 Hz 遥测与仪表板；600 秒验收无消息丢失。 |
| 8：姿态表征 | PASS / REFERENCE_LIMITED | 噪声、漂移、动态比较、候选参数排序；手机水平仪仅作辅助参考。 |
| 9A：安全 PWM | PASS | 显式 Arm、ESTOP、超时、限幅、斜率限制、单一控制 Owner。 |
| 9B：姿态驱动 PID | PASS_WITH_WARNINGS | STM32 本地 100 Hz PID、Roll/Pitch 选择、反向方向、死区、D 项滤波、反积分饱和、MQTT 配置/波形。机构姿态闭环指标不适用。 |
| 10：配置持久化/发布 | PASS（当前为未提交改动） | 双槽 Flash、CRC、出厂复位、安全启动、资源门禁、CI/发布资料。 |

当前验证：`tools/test-phase10.ps1`、`tools/check-phase10.ps1`、`tools/check-release.ps1` 在 2026-08-17 均通过；Python 测试为 129 项通过。Debug 固件 62,272 / 63,488 B，余量仅 1,216 B；RAM 17,824 / 18,944 B，余量 1,120 B，因此后续功能必须先做资源预算。

已知限制：PWM 电气抖动未测试；舵机电流遥测未提供；本地 MQTT 无 TLS，不能暴露到公网；历史 `phase09/closed-loop` 记录明确标为 `CLOSED_LOOP_PLANT_NOT_AVAILABLE`。

## 4. 代码导航

| 目录 | 职责 |
| --- | --- |
| `Src/`、`Inc/`、`MotionEdge-F103.ioc` | CubeMX 生成的启动与外设配置；不要改自动生成区。 |
| `BSP/`、`Devices/` | HAL 适配：UART、I2C、PWM、Flash、MPU6500。 |
| `Algorithms/`、`Components/` | 无 HAL 的滤波、姿态、PID 与舵机数学模型。 |
| `Services/` | 校准、传感、通信、配置、控制、执行器、遥测等业务服务。 |
| `App/RTOS/` | 应用装配和四个 FreeRTOS 任务。 |
| `Middleware/`、`Common/` | 协议、CRC、环形缓冲、日志、CSV、软件定时器。 |
| `host/motionctl/` | 串口工具、网关、MQTT、报告与实验。 |
| `node-red/` | MQTT Flow 和浏览器仪表板。 |
| `Tests/Host/`、`host/tests/`、`tools/` | C/Python 测试、构建、硬件验收和发布检查。 |
| `artifacts/` | 已有验收证据；不应由业务代码读取。 |

## 5. 推荐优化阶段

1. **阶段 A：冻结 v1.0、文档和基线整顿。** 先把 Phase 10 未提交内容做完整构建、回归和一次真实硬件复验，提交可追溯基线；统一 README、阶段报告中的“姿态感知反向跟随”术语。
2. **阶段 B：反向跟随体验优化。** 依据手持姿态与舵机方向，校正 Roll/Pitch 轴、零位、正反方向、死区、响应曲线、斜率和 PID 参数，形成稳定可演示的交互体验。
3. **阶段 C：控制品质与安全验证。** 增加人工姿态阶跃、正反向、死区、饱和、传感器断线、串口/MQTT 断开、卡滞和供电跌落测试；以可复现 CSV 报告量化响应延迟、PWM 抖动、输出一致性与故障安全行为。
4. **阶段 D：观测与物联网产品化。** 完善参数编辑/回读、波形导出、报警、实验记录；如需远程访问，再引入鉴权、TLS、ACL 和禁止公网裸露。
5. **阶段 E：可选的机构闭环升级。** 只有在项目后续加入受舵机驱动的机械平台及反馈传感器/编码器时，才进行真正的机构姿态闭环、阶跃超调和稳态误差优化。
6. **阶段 F：资源与硬件演进。** Debug Flash/RAM 余量很小；为更多滤波、缓存、TLS 或双 IMU 评估 STM32F103C8 的容量和供电/EMI，再决定优化或换 MCU。

## 6. 可直接使用的 Codex 指令

### A. 建立 v1.0 冻结基线

```text
在 C:\\STM32\\MotionEdge-F103 中完成“v1.0 冻结基线”整理。先阅读 AGENTS.md、README.md、docs/current-project-status-and-roadmap.md、docs/config-persistence.md 及 tools/check-phase10.ps1。不得修改 CubeMX 自动生成区，不得使用动态内存，HAL 只能在 BSP/驱动适配层。检查当前未提交的 Phase 10 持久化改动是否完整；运行 Debug/Release 构建、tools/test-phase10.ps1、tools/check-phase10.ps1、tools/check-release.ps1。只修复有测试或编译证据的问题；更新版本、变更日志、验证报告和 README 的事实不一致处。不要把单 MPU6500 手持输入描述成外部机械闭环。最后列出修改文件、测试结果、固件 Flash/RAM 余量，以及仍需实机验证的项目。
```

### B. 优化姿态感知反向舵机跟随

```text
优化 MotionEdge-F103 的“姿态感知 PID 反向舵机跟随”功能：MPU6500 由用户手持，SG90 不带动传感器。阅读 ControlService、ActuatorService、SensorService、pid_controller、协议、motionctl 和 Node-RED 代码。梳理并实现可配置的控制轴（Roll/Pitch）、方向（normal/reverse）、相对零位、死区、响应曲线、PID 参数、输出限幅和斜率；确保 STM32 SensorTask 100 Hz 本地执行，MQTT/Node-RED 只负责低频配置和观测。保持上电未 Arm、传感器失效/超时/ESTOP 安全停机、网关断开不影响本地控制。先为每项行为写主机 C/Python 测试，再输出人工手持姿态实验的 CSV、延迟/输出一致性指标和波形。文档必须称其为姿态感知反向跟随，不得称为机构姿态闭环或自平衡。
```

### C. 验收反向跟随的演示质量与安全性

```text
为 MotionEdge-F103 建立“姿态感知 PID 反向舵机跟随”的实机验收流程。硬件前提为 SG90 独立稳压 5 V、与 STM32 共地、转动范围无遮挡且 ESTOP 可触达；MPU6500 由人手持输入，不要求舵机影响传感器。保持 1450–1550 us 绝对窗口、显式 Arm、命令超时、ESTOP、传感器离线和 App Fault 联锁。通过 Roll/Pitch 正反向动作、零位、死区、小/大幅输入、连续动作、传感器断线、串口/MQTT 断开和 600 秒稳定性测试，输出原始 CSV、指标 JSON 和图表。指标包括姿态到 PWM 的方向正确率、延迟、输出范围、死区抑振效果、PWM 抖动、控制频率与故障安全行为；不报告或推断机构闭环的超调、调节时间和稳态误差。
```

### D. 完善物联网调参和波形

```text
改进 MotionEdge-F103 的本地 MQTT/Node-RED 调参与波形功能。保留本地 broker 默认绑定和非实时控制边界。实现 PID 参数的表单输入、范围校验、设备回读、dirty/已保存状态、一次性 request_id、命令响应关联和 CSV 导出；展示目标角、测量角、误差、P/I/D、PWM、模式和故障状态。命令必须非 retained、具备过期时间和去重，网关断开不得影响 STM32 的 100 Hz 控制。为 MQTT 模型、网页数据处理和导出功能补 Python/前端测试；若要上公网，先单独设计 TLS、身份认证和 ACL，不要直接暴露现有 broker。
```

### E. 资源与可靠性优化

```text
对 MotionEdge-F103 做一次不改变功能语义的资源与可靠性优化。以当前 Debug Flash 62272/63488 B、RAM 17824/18944 B 为容量红线，先生成模块级尺寸和静态 RAM 预算。优先消除重复代码、过大缓冲、未使用符号和不必要日志，不使用 malloc/calloc/realloc，不通过关闭警告或删除安全检查来压缩。保持 CubeMX 自动生成区不变，HAL 仅留在 BSP/驱动层。每项优化要给出前后 Debug/Release 大小、C/Python 回归结果、协议兼容性影响和回退方案；没有明确收益就不要重构。
```
