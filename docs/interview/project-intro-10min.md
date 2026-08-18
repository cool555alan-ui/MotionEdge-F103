# MotionEdge-F103 十分钟深度介绍

## 1. 项目目标（约 45 秒）

MotionEdge-F103 是基于 STM32 的姿态感知与物联网控制平台。目标是把“MPU6500 采集 → 姿态估计 → FreeRTOS 实时调度 → PID 计算 → SG90 安全输出”与“Binary Protocol → Python → MQTT → Node-RED”两条链连接起来，再用双槽 Flash、测试、CI 和 Release 保证可复现。

我先主动声明边界：MPU6500 是手持输入，SG90 不带动传感器，所以项目不是自平衡或外部机械姿态反馈闭环。它展示的是姿态感知、控制计算和安全执行器响应。

**老师可能打断：**“没有机械闭环为什么还用 PID？”先回答模块完整支持 PID，但最终根据对象采用 Ki=0 的 PD 配置，重点是受限映射、D 项抑制和工程安全。

## 2. 硬件（约 45 秒）

主控 STM32F103C8T6，MPU6500 走 I²C1 PB6/PB7，实机地址 `0x68`、WHO_AM_I `0x70`；CH340 连接 USART1 PA9/PA10、115200 bit/s；SG90 信号是 TIM3_CH1 PA6、50 Hz。舵机使用独立稳压 5 V，与 STM32 共地，避免启动电流干扰 MCU 和传感器。

**老师可能打断：**“为什么不用 MCU 5 V？”说明舵机瞬态电流和电源噪声风险，独立供电与共地是信号完整性和可靠性要求。

## 3. 姿态链（约 75 秒）

上电先识别传感器，再收集 500 samples 做静态零偏校准。500 样本在 100 Hz 下约 5 秒，兼顾平均噪声和启动时间。加速度计长期有重力参考但动态噪声大，陀螺仪短期响应好但积分漂移，所以先做 alpha 0.20 的低通，再以 gyro weight 0.98 做互补融合，输出 Roll/Pitch。

没有 Yaw 是有意边界：六轴 IMU 无磁力计，重力无法约束绕重力轴旋转。Phase 8 得到 Roll/Pitch MAE 0.352°/0.375°、静态标准差 0.019°/0.016°；MAE 使用 iPhone 水平仪参考且不确定度未知，所以是 `REFERENCE_LIMITED`，不是绝对精度。

**老师可能打断：**“为什么不用 Kalman？”回答当前六轴、100 Hz、F103 资源和实测效果下，互补滤波状态少、参数可解释、易验证；若加入磁力计或更复杂模型再评估 EKF。

## 4. FreeRTOS（约 70 秒）

四个静态任务分别是 Sensor 100 Hz、Communication ~500 Hz、Telemetry 10 Hz、Health 1 Hz。SensorTask 完成 sampling、attitude、control；CommunicationTask 快速服务 UART/parser；TelemetryTask 降采样输出；HealthTask 汇总 deadline、stack 和错误。

任务之间：Queue 传递有序命令，Mutex 保护一致的 Motion snapshot，Event Flag 广播 ready/calibrated/fault。没有 ControlTask，因为 PID 应消费同周期新姿态，额外任务会增加栈、切换和同步相位。历史代表实测是 100.003/500.012/10.001/1.000 Hz，独立 600 s 记录通过。

**老师可能打断：**“500 Hz 是不是过度？”说明它是 2 ms 轮询服务周期，不是传感/网络频率；目标是减少 UART backlog，CPU 仍由阻塞延时调度。

## 5. Binary Protocol（约 55 秒）

协议包含 version、type、flags、sequence、payload length 和 CRC16-CCITT-FALSE。Parser 按流处理半帧、粘包、噪声、非法长度和 CRC 错误；CommandService 再检查 payload、范围、状态和 Owner。二进制比 JSON 更省 Flash/RAM 和解析时间，也更容易生成 C/Python golden vectors。

CRC 只检测传输错误，不提供认证。若公网部署，安全应由 TLS、设备身份和 ACL 负责。

**老师可能打断：**“错帧怎么恢复？”说明限制长度、CRC 验证、丢弃错误候选并重新寻找同步头，而不是把任意字节解释为命令。

## 6. PID 与安全（约 90 秒）

完整 Controller 支持 P/I/D、D 滤波、积分模式、anti-windup 和限幅。最终参数 Pitch、Kp 1.0、Ki 0、Kd 0.05、D alpha 0.2、deadband 1.0°、output ±10 µs。

Ki=0 是对象决定的：如果用户持续手持 10°，舵机不会把 MPU6500 拉回，积分只能持续累加到限幅，所以最终采用 PD。D 项对噪声敏感，用 alpha 0.2 低通。人工输入对比中，P-only PWM 输出标准差 5.555 µs，PD 是 2.535 µs，下降 54.4%；这是 PWM 统计，不能说闭环超调或机械抖动下降。

ActuatorService 独立执行 Arm、Owner、Timeout、Clamp、Slope 和 ESTOP。安全窗口 1450/1500/1550 µs；传感器离线、样本 stale、App Fault 或 ESTOP 都回到安全路径。

**老师可能打断：**“SG90 自己是不是闭环？”回答其内部可能有位置控制，但项目没有测量其内部轴角，也没有把该位置反馈给 STM32 的外层控制，因此不能把内部伺服等同于项目的机械外环。

## 7. IoT（约 65 秒）

Python `motionctl` 提供 doctor、命令、采集和报告；Gateway 独占串口并映射 MQTT；Node-RED 展示姿态、P/D 项和 PWM。命令非 retained、带过期和 request_id 去重。QoS 1 提供确认但允许重复，所以去重不可少。

Phase 7 稳定窗口是 4934/4934，Gateway 到 Node-RED local P95 2 ms，Broker recovery 2.80 s。PING command RTT P95 216.58 ms 是另一条路径，不能混为 telemetry latency。PID 在 STM32 本地，所以 Broker 中断不影响 100 Hz 控制。

**老师可能打断：**“MQTT 是不是堆技术？”回答它负责设备与 UI 解耦、多订阅者和状态/命令契约；但单机实时控制不会放到 MQTT 上。

## 8. Flash Persistence（约 60 秒）

配置区 2048 B，两个 1 KiB Slot，Record 54 B、Schema 1。CRC 检测损坏，commit marker 最后写入判断完整提交，generation 选择更新槽。真实断电覆盖保存恢复、RAM-only 丢弃、槽切换和 Factory Reset；FakeFlash 覆盖部分写与损坏。

Arm、Owner 和 PID Enable 不持久化，上电总是 Control Disabled、Actuator Disarmed、Owner NONE、PWM 1500 µs。

**老师可能打断：**“CRC 和 marker 是否重复？”回答 CRC 判断内容正确，marker 判断事务是否完成；半写内容即使局部看似合理也不能成为已提交记录。

## 9. 实验与工程结果（约 70 秒）

验证分层：纯算法/协议用 Host C 和 Python；硬件状态、RTOS、舵机、掉电、MQTT 用实机；人工输入明确 `HUMAN_INPUT_LIMITED`。v1.0 最终验收 624.742 s，Sensor deadline delta 1、其他任务 0，未发生 reset/fault/数据损坏/控制失败，保留 warning。

v1.0.1 资源优化把 HAL/FreeRTOS Debug 改成 `-Os`，应用仍是 `-Og -g3`。Debug Flash 从 62308 B 到 59240 B，节省 3068 B、余量 4248 B；没有缩 Stack、Queue、Buffer 或安全逻辑，也没有用 LTO。

**老师可能打断：**“600 秒够吗？”回答它只证明阶段场景内连续运行与错误计数，不代表工业寿命、温度、EMC 或批量一致性。

## 10. 问题、改进与总结（约 45 秒）

项目最明显的不足是没有机械外环、Yaw 不可观、参考受限、PWM 电气抖动和舵机电流未测、本地 MQTT 无 TLS、F103 RAM 余量有限。下一步有意义的改进是做单轴机械平台，加入编码器或第二 IMU；功能继续扩展时换更高资源 MCU；公网部署前补 TLS/ACL。

我认为项目最有价值的地方不是功能数量，而是每项能力都有边界、失败状态和 evidence：能说明数字怎么来，也能明确什么没有被证明。
