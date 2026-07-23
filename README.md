# MotionEdge-F103

MotionEdge-F103 是基于 STM32F103C8T6 和 MPU6050 的嵌入式运动控制基础项目。

- MCU：STM32F103C8T6
- 传感器：MPU6050（尚未接入固件）
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

## 常用命令

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\test-host.ps1
powershell -ExecutionPolicy Bypass -File .\tools\build.ps1
powershell -ExecutionPolicy Bypass -File .\tools\check-phase1.ps1
```
