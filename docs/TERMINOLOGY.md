# MotionEdge-F103 术语规范

## 项目名称

- 正式英文名：**MotionEdge-F103**。
- 正式中文名：**基于 STM32 的姿态感知与物联网控制平台**。
- 简历空间有限时：**基于 STM32 的姿态感知与 IoT 控制平台**。

## 推荐术语

| 中文语义 | 推荐英文 | 使用说明 |
|---|---|---|
| 姿态感知 | attitude sensing | MPU6500 采集与姿态链入口 |
| 姿态估计 | attitude estimation | 校准、低通、互补融合得到 Roll/Pitch |
| 基于 PID 的姿态驱动舵机控制 | PID-based attitude-driven servo control | 当前控制功能正式名称 |
| 最终 PD 配置 | final PD configuration | Controller 完整支持 PID，但 Ki=0 |
| 控制链 | control chain | 姿态感知 → 计算 → 执行器输出 |
| 本地 MQTT 原型 | local MQTT prototype | 无 TLS，不暴露公网 |
| 参考受限表征 | reference-limited characterization | 手机水平仪参考不确定度未知 |
| PWM 安全窗口 | safe PWM window | 1450–1550 µs |
| 双槽持久化 | dual-slot persistence | CRC、generation、commit marker |

## 禁止或谨慎使用

| 表述 | 问题 | 正确替代 |
|---|---|---|
| high precision / 高精度 | 没有计量级参考 | `REFERENCE_LIMITED` 工程比较 |
| industrial grade / 工业级 | 600 s 不是寿命与认证 | 已完成 600 s 实机稳定性记录 |
| closed-loop attitude stabilization / 姿态闭环稳定 | SG90 不改变 MPU6500 姿态 | 姿态驱动舵机控制 |
| self-balancing / 自平衡 | 没有机械平台外环 | 手持姿态输入与舵机响应演示 |
| absolute accuracy / 绝对精度 | 手机参考不确定度未知 | 相对手机参考的 MAE |
| cloud platform / 云平台 | 当前只有本地 Mosquitto | 本地 MQTT/Node-RED 原型 |
| real-time cloud control | 实时控制在 MCU | 远程配置与观测，本地实时控制 |
| zero loss forever | 只验证有限窗口 | 600 s 稳定窗口 4934/4934 |
| hardware-level five protections | 含义模糊且不可审计 | 逐项写 Arm、Owner、Timeout、Clamp、ESTOP |

## 三个易混淆数字

- `0.352°/0.375°`：相对 iPhone 水平仪的 Roll/Pitch MAE，`REFERENCE_LIMITED`，不是绝对精度。
- `54.4%`：P-only 与 PD 两次人工输入实验的 **PWM 输出标准差**下降，不是机械抖动、超调或总体性能提升。
- `2 ms`：Gateway → Node-RED 本地接收 P95；`216.58 ms` 才是 PING command round-trip P95。

## 控制边界标准回答

“本项目的 MPU6500 测量用户手持板姿态，PID 根据相对零位误差计算 SG90 PWM；舵机运动不会反向改变该传感器姿态，因此我把它定义为基于 PID 的姿态驱动舵机控制，而不是外部机械姿态反馈闭环。若后续加入舵机驱动平台并把 IMU 或编码器装到被控机构上，才具备讨论机构超调、调节时间和稳态误差的条件。”
