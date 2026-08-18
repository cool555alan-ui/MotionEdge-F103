# MotionEdge-F103 一分钟介绍

MotionEdge-F103 是我基于 STM32F103 和 MPU6500 做的姿态感知与物联网控制平台。嵌入式主链是 MPU6500 采集六轴数据，经过 500 样本校准、低通和互补滤波，以 100 Hz 输出 Roll/Pitch；FreeRTOS 用四个任务隔离采样、通信、遥测和健康监控。姿态误差在 MCU 本地进入 PID 模块，最终使用 Kp 1.0、Ki 0、Kd 0.05 的 PD 配置，经安全状态机驱动 SG90。这里舵机不带动传感器，所以我不把它称为机械姿态闭环。设备通过 CRC16 二进制串口连接 Python Gateway，再接本地 MQTT 和 Node-RED。验证中，参考受限的 Roll/Pitch MAE 是 0.352°/0.375°，MQTT 稳定窗口是 4934/4934，v1.0.1 又节省了 3068 B Debug Flash。这个项目最大的收获，是把算法、实时系统、IoT 和可验证的安全边界做成了同一套工程。

正常语速约 60 秒。MAE 必须连同“iPhone 参考、`REFERENCE_LIMITED`”说明；若老师追问控制边界，立即说明没有舵机输出到 MPU6500 的机械反馈。
