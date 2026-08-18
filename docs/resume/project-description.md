# 简历项目描述

## 三种约 80 字定位

### 姿态与控制版

基于 STM32F103 与 MPU6500 构建 100 Hz 姿态感知和 PD 舵机控制链，实测 Roll/Pitch MAE 0.352°/0.375°，PD 将 PWM 波动降低 54.4%，并以 Arm/ESTOP/限幅保证演示安全。

### RTOS 与嵌入式版

在 STM32F103 上以 FreeRTOS 解耦 100 Hz 传感控制、500 Hz 通信、10 Hz 遥测和 1 Hz 健康任务；完成 600 s 稳定性与 624.742 s 系统验收，栈溢出、动态内存失败和复位均为 0。

### 边云与工程化版

实现 STM32 二进制协议、UART DMA、Python CLI、MQTT Gateway 与 Node-RED 可视化，稳定区间 4934/4934 帧零丢失，Broker 约 2.80 s 恢复，并以 CI、证据索引和指标事实源管理发布质量。

## 精简版要点（每条约 55–65 字）

- 设计 MPU6500 互补滤波与 100 Hz 姿态链，对有限 iPhone 参考取得 Roll/Pitch MAE 0.352°/0.375°，并明确结果为 REFERENCE_LIMITED。
- 实现支持 P/I/D 的姿态驱动舵机控制，实测采用 Kp=1.0、Ki=0、Kd=0.05 的 PD 配置，使 PWM 标准差下降 54.4%。
- 基于 FreeRTOS 拆分传感、通信、遥测与健康任务，独立 600 s soak 中栈溢出和 malloc failure 均为 0。
- 打通 UART DMA、Python CLI、MQTT 与 Node-RED，稳定区间 4934/4934 帧零丢失，Broker 恢复约 2.80 s。

## 详细版要点（每条约 100–120 字）

- 面向 STM32F103C8T6 资源约束，完成 MPU6500 采样、互补滤波、坐标约定和校准链路；以 100 Hz 生成姿态，有限 iPhone 参考下 Roll/Pitch MAE 为 0.352°/0.375°，同时保留参考不确定度未知的 REFERENCE_LIMITED 边界。
- 设计“姿态感知 → PID 控制计算 → 执行器输出”链路，控制器支持 P/I/D，实机最终采用 Kp=1.0、Ki=0、Kd=0.05；通过导数滤波、±10 µs 增量和 1450–1550 µs 安全窗，将 PWM 标准差由 5.555 µs 降至 2.535 µs。
- 以 FreeRTOS 组织 100 Hz 传感控制、500 Hz 通信、10 Hz 遥测和 1 Hz 健康路径，建立 deadline、任务心跳、栈溢出和动态内存失败观测；独立 600 s soak 无栈/内存故障，系统终验持续 624.742 s 且无复位、Fault 或控制失败。
- 构建二进制串口协议、512 B UART circular DMA、Python CLI、MQTT Gateway 与 Node-RED 仪表；稳定区间网关和 Node-RED 均接收 4934/4934 帧，同机链路 P95 为 2 ms，Broker 故障后约 2.80 s 恢复，网络不进入本地实时控制必经路径。

## 表述边界

SG90 不带动 MPU6500，因此项目不是自平衡机构或外部机械姿态闭环。0.352°/0.375° 只描述有限参考对比，不写成传感器绝对精度；54.4% 只描述指定人工输入实验中的 PWM 波动改善。
