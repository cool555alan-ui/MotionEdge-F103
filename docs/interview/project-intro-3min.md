# MotionEdge-F103 三分钟介绍

## 0–30 秒：项目是什么

老师您好，我的项目叫 MotionEdge-F103，是基于 STM32 的姿态感知与物联网控制平台。我想做的不只是“读一个 IMU”，而是把传感、实时调度、控制、安全执行、设备协议、Python 工具、MQTT 监控和 Flash 持久化串成一条可验证链路。系统使用 STM32F103C8T6、MPU6500 和 SG90，实时控制全部在 MCU 本地完成。

## 30–90 秒：嵌入式主链

MPU6500 通过 I²C 采集六轴数据，上电先做 500 样本静态校准，再用 alpha 0.20 的低通和陀螺仪权重 0.98 的互补滤波计算 Roll/Pitch。采样和姿态更新是 100 Hz。FreeRTOS 分成 Sensor、Communication、Telemetry、Health 四个任务，其中 SensorTask 同步完成采样、姿态和控制，没有再建 ControlTask，这样可以减少任务栈和切换，也避免控制使用上一周期数据。

姿态相对零位误差进入完整 PID 模块，最终实验选择 Kp 1.0、Ki 0、Kd 0.05 的 PD 配置。Ki 设为 0 是因为舵机不会反向改变手持 MPU6500 的姿态，持续输入不应该让积分不断累积。执行器还有显式 Arm、Owner、Timeout、ESTOP、±10 µs PID 输出限制和 1450–1550 µs 绝对 PWM 窗口。相较 P-only，PD 实验的 PWM 输出标准差从 5.555 µs 降到 2.535 µs，约 54.4%；这里我只描述 PWM 统计，不把它说成机械抖动或闭环超调。

## 90–140 秒：协议与 IoT

STM32 使用带 CRC16 的二进制协议连接 Python `motionctl`。选择二进制而不是串口 JSON，是为了控制 F103 上的解析开销和缓冲大小，并能明确处理半帧、粘包和错帧。Python Gateway 把设备数据转成 MQTT，Node-RED 展示 Roll/Pitch、PID 项和 PWM，也能做低频配置。实时 PID 不经过网络，所以 Broker 掉线不会中断 MCU 控制。Phase 7 的稳定窗口 Gateway 和 Node-RED 都收到 4934 帧，Gateway 到 Node-RED 本地 P95 是 2 ms，Broker 恢复是 2.80 s。

## 140–170 秒：工程可靠性

配置持久化使用两个 1 KiB Flash 槽，记录包含 Schema 1、CRC、generation 和最后写入的 commit marker，真实掉电、槽切换、Factory Reset 和安全启动都验证通过。上电不会恢复 Arm、Owner 或 PID Enable，默认回到 PWM 1500 µs。项目还有 Host C/Python 测试、Debug/Release、Flash overlap gate、CI 和版本化 Release。v1.0.1 没缩 Stack、Queue 或 Buffer，只把稳定的 HAL/FreeRTOS Debug 代码改为 `-Os`，节省 3068 B Flash。

## 170–180 秒：总结

我最重要的收获，是学会先界定系统能证明什么，再用代码分层、故障安全和 evidence 把算法结果变成可追溯工程，而不是堆功能或夸大指标。
