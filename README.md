# MotionEdge-F103

MotionEdge-F103 是基于 STM32F103C8T6 和 MPU6050 的嵌入式运动控制基础项目。

- MCU：STM32F103C8T6
- 传感器：MPU6050
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

当前没有连接硬件，尚未进行烧录验证。LED 电平行为、USART1 实际输出和 ST-LINK
连接仍需在目标板上验证。

详细设计和验证边界见
[第一阶段固件基础框架](docs/phase-01-firmware-foundation.md)。

## Phase 2: I²C and MPU6050

第二阶段增加了：

- I²C1 BSP 寄存器读写和有限超时设备探测
- 每次主循环仅探测一个地址的非阻塞 I²C 扫描状态机
- 与 STM32 HAL 解耦的 MPU6050 驱动
- `WHO_AM_I` 身份读取与校验
- 电源管理寄存器唤醒
- 加速度计和陀螺仪六轴原始数据读取
- 使用模拟 I²C 总线的 Windows 主机测试

当前未连接目标硬件。上述逻辑已经通过主机测试和 STM32 交叉编译，但总线电气连接、
地址响应、`WHO_AM_I` 实际值和六轴采样仍需连接 MPU6050 后验证。

详细说明见 [第二阶段 I²C 与 MPU6050](docs/phase-02-i2c-mpu6050.md)。

## 常用命令

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\test-host.ps1
powershell -ExecutionPolicy Bypass -File .\tools\build.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase1.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase2.ps1
```
