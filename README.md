# MotionEdge-F103

MotionEdge-F103 是基于 STM32F103C8T6 和 MPU6050/MPU6500兼容驱动的嵌入式运动控制基础项目。当前实板器件为MPU6500（WHO_AM_I=`0x70`）。

- MCU：STM32F103C8T6
- 传感器：MPU6500
- 开发环境：STM32CubeMX + STM32CubeIDE for Visual Studio Code
- 构建系统：CMake + GCC
- 不使用 Keil、PlatformIO 或传统 STM32CubeIDE 桌面版
- 当前固件与Python工具版本：`0.6.0`（Phase 6 实机验证通过）

## Phase 1: Firmware Foundation

第一阶段建立了以下固件基础能力：

- PC13 低电平有效板级 LED 封装
- USART1 有限超时日志输出接口
- 与 HAL 解耦的固定缓冲区 Logger
- 支持 32 位毫秒计数器回绕的软件定时器
- 应用状态管理
- 运行时间、循环、心跳和日志错误健康统计
- Windows 主机侧纯 C 单元测试
- STM32 CMake Debug 交叉编译

2026-08-02 已在 STM32F103C8T6 实板完成 ST-LINK 连接、下载校验、复位启动和
USART1 日志验证。健康日志中的心跳计数正常递增；PC13 LED 的实际亮灭极性仍需目视确认。

详细设计和验证边界见
[第一阶段固件基础框架](docs/phase-01-firmware-foundation.md)。

## Phase 2: I²C and MPU6500

第二阶段增加了：

- I²C1 BSP 寄存器读写和有限超时设备探测
- 每次主循环仅探测一个地址的非阻塞 I²C 扫描状态机
- 与 STM32 HAL 解耦的 MPU6500 驱动
- `WHO_AM_I` 身份读取与校验
- 电源管理寄存器唤醒
- 加速度计和陀螺仪六轴原始数据读取
- 使用模拟 I²C 总线的 Windows 主机测试

2026-08-02 实板验证发现 I²C 地址 `0x68`、`WHO_AM_I=0x70`，传感器能够唤醒并持续
输出六轴数据。验证证据见 `artifacts/hardware-validation/`。

详细说明见 [第二阶段 I²C 与 MPU6500](docs/phase-02-i2c-mpu6500.md)。

## Phase 3: Calibration and Attitude Pipeline

第三阶段完成了：

- 100 Hz缩放样本采集与数据质量检查
- 500样本非阻塞静止校准和RAM偏差结果
- 六轴一阶低通滤波
- 加速度Roll/Pitch、陀螺仪积分和互补滤波
- 0.01°整数姿态输出和100 ms限频CSV遥测
- Python模拟、校验、汇总、回放和串口记录工具
- C主机算法测试和Python工具测试
- STM32 CMake Debug交叉编译

实板已完成500样本静止校准、CSV姿态输出以及左右/前后倾斜响应验证。静止加速度模长
均值约为1 g，Roll/Pitch随动作明显变化；绝对角度精度、温漂和长期漂移仍待治具及长时间测试。

详细说明见[第三阶段校准与姿态数据链](docs/phase-03-calibration-attitude.md)。

## Phase 4: Binary Device Protocol

第四阶段增加 CRC16-CCITT-FALSE、固定内存二进制帧、字节环形缓冲区、可恢复流式
Parser、统一命令响应、RAM 运行时配置、二进制 Motion/Health 遥测，以及
`python -m motionctl` 设备 CLI 和无硬件模拟器。协议模式启用后 USART1 只发送
二进制帧，避免与普通日志和 CSV 混流。

软件协议、模拟设备、主机测试和 STM32 GCC 交叉编译已完成。

2026-08-05 实板二进制命令验证：PING、设备信息、状态、运行时配置读写、最新姿态查询、
流控制全部 PASS；串口解析错误、CRC 错误、RX 溢出均为 0。二进制帧与文本日志/CSV 严格
隔离，协议模式下未出现混流。

详细格式和验证边界见[协议规范](docs/protocol-specification.md)和
[第四阶段记录](docs/phase-04-device-protocol.md)。

## Phase 5: FreeRTOS Scheduling Migration

第五阶段使用CubeMX生成的FreeRTOS 10.3.1和CMSIS-RTOS2，将原裸机协作调度迁移为
SensorTask、CommunicationTask、TelemetryTask和HealthTask。驱动、算法、协议和服务
保持RTOS无关；任务、命令队列、互斥锁、事件标志及运动快照使用静态存储。

2026-08-05 实板验收通过（41 PASS / 0 WARN / 0 FAIL），关键实测数据：

- **任务频率**：SensorTask 100.003 Hz、CommunicationTask 500.012 Hz、
  TelemetryTask 10.001 Hz、HealthTask 1.000 Hz
- **600 秒独立稳定性**：6001 帧，100 ms 固定间隔，sequence 固定 +10，
  丢帧/回退/解析错误均为 0；状态全程 RUNNING，DEGRADED/FAULT 0 次
- **稳定段 Deadline miss**：0/0/0/0（校准期间 SensorTask 有少量 transient miss，
  校准完成后清零）
- **栈高水位**：最低剩余 284 B（TelemetryTask），所有任务栈余量充足
- **堆最低剩余**：2,440 B；栈溢出/malloc 失败 0
- **传感器掉线恢复**：断开→DEGRADED→重新识别→唤醒→校准→RUNNING，全自动
- **二进制命令**：PING/INFO/STATUS/CONFIG/MOTION/STREAM 全部 PASS
- **资源**：Debug Flash 45,620 B（69.6%），RAM 16,328 B（79.7%）

验证证据见 `artifacts/rtos-validation/rtos-validation-report.md` 和
`stability-soak-summary.json`。

详细说明见[第五阶段迁移记录](docs/phase-05-freertos-migration.md)和
[RTOS任务设计](docs/rtos-task-design.md)。

## Phase 6: Python Device Tools

第六阶段将现有二进制协议包装为`motionctl 0.6.0`设备工具，提供端口枚举、设备诊断、
信息/状态/配置、校准、流控制、实时监视、原子采集、离线校验、一键会话及自动报告。
协议、Transport、设备请求、数据模型、统计、规则、报告和模拟器职责独立；固件协议未提供
的字段明确显示`NOT_AVAILABLE`。

```powershell
python -m pip install -e .\host
python -m motionctl ports
python -m motionctl doctor --port COM4
python -m motionctl session --port COM4 --duration 60 --output artifacts/phase06/final-validation
```

采集链同时保存设备时间和主机单调时间，自动生成Markdown、JSON、metrics CSV、姿态曲线
和遥测间隔曲线。模拟器测试、离线报告测试和真实串口验收在证据中严格区分。

2026-08-05 使用COM4上的CH340和真实STM32F103C8T6/MPU6500完成最终验收：逻辑PING
100/100成功（1次线路瞬态超时由只读安全重试恢复）；干净采集60.0秒、601帧、
10.0167 Hz，设备时间间隔固定100 ms，sequence固定+10，丢帧、重复、回退、主机CRC和
Parser错误均为0。Roll范围-27.04°～33.35°，Pitch范围-40.58°～25.81°，平均加速度
模长1001.75 mg；串口关闭1秒后重新打开并PING成功。最终证据位于
`artifacts/phase06/final-validation/`。

详细说明见[Phase 6设备工具](docs/phase-06-python-device-tools.md)、
[CLI参考](docs/motionctl-cli-reference.md)和[报告格式](docs/automated-report-format.md)。
下一阶段为Phase 7 MQTT网关与Node-RED，本阶段不包含这两项功能。

## Phase 7: MQTT Gateway and Node-RED

Phase 7 keeps firmware at `0.6.0` and updates the Windows `motionctl` gateway to `0.7.0`. The path is MPU6500 -> STM32F103/FreeRTOS -> CRC16 serial protocol -> Python gateway -> local Mosquitto -> Node-RED. Topic, startup, dashboard, and validation details are in [the gateway guide](docs/phase-07-mqtt-gateway.md), [topic contract](docs/mqtt-topic-contract.md), [Node-RED guide](docs/node-red-dashboard.md), and [validation method](docs/phase-07-validation-method.md).

## Phase 8: attitude characterization

Phase 8 keeps firmware at `0.6.0` and updates `motionctl` to `0.8.0`. It adds real-device Roll/Pitch static accuracy, noise, drift, manual dynamic comparison, online RuntimeConfig candidate validation, transparent ranking, and report generation. The MPU6500 is a six-axis IMU, so absolute Yaw is intentionally outside the observable boundary. Run `python -m motionctl characterize --help`, `python -m motionctl tune --help`, and `tools\check-phase8.ps1` for the reproducible workflow.

The isolated development broker binds only to `127.0.0.1:1884`; TLS is disabled, so it is not a public-cloud or production deployment. Phase 8 is attitude accuracy and parameter tuning, not actuator control.

```powershell
.\tools\start-phase07-broker.ps1
.\tools\start-phase07-node-red.ps1
.\tools\import-node-red-phase07.ps1
python -m motionctl gateway run --config .\config\motionedge-gateway.toml
```

## 常用命令

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\test-host.ps1
powershell -ExecutionPolicy Bypass -File .\tools\build.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase1.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase2.ps1
powershell -ExecutionPolicy Bypass -File .\tools\test-python.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase3.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase4.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase5.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase6.ps1
powershell -ExecutionPolicy Bypass -File .\tools\test-phase6.ps1
```
