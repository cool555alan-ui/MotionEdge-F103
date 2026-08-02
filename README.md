# MotionEdge-F103

MotionEdge-F103 是基于 STM32F103C8T6 和 MPU6500 的嵌入式运动控制基础项目。

- MCU：STM32F103C8T6
- 传感器：MPU6500
- 开发环境：STM32CubeMX + STM32CubeIDE for Visual Studio Code
- 构建系统：CMake + GCC
- 不使用 Keil、PlatformIO 或传统 STM32CubeIDE 桌面版

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

软件协议、模拟设备、主机测试和 STM32 GCC 交叉编译已完成；这不等于真实串口验证
完成。真实 USART 收发、帧传输、命令响应和长时间通信仍需在面包板上验证。

详细格式和验证边界见[协议规范](docs/protocol-specification.md)和
[第四阶段记录](docs/phase-04-device-protocol.md)。

## 常用命令

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\test-host.ps1
powershell -ExecutionPolicy Bypass -File .\tools\build.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase1.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase2.ps1
powershell -ExecutionPolicy Bypass -File .\tools\test-python.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase3.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase4.ps1
```
