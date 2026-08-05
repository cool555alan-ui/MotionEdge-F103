# Phase 6：Python设备工具

Phase 6在已通过FreeRTOS实机验收的固件上提供可复现的Windows设备管理流程，不增加RTOS任务，也不涉及MQTT、Node-RED、PWM或PID。

## 架构

- `protocol.py`：唯一的Frame、CRC16和流式Parser实现。
- `transport.py`：Transport接口、pyserial适配和可注入MemoryTransport。
- `device.py`：sequence匹配、异步遥测分流、单调时钟超时和安全重试。
- `models.py` / `commands.py`：带单位数据模型和协议载荷编解码。
- `capture.py`：流式CSV、原始字节证据、临时文件及原子重命名。
- `metrics.py`：离线纯逻辑统计，支持从主导步长推断固定`+10` sequence。
- `validation.py` / `validation_profile.py`：统一分级和集中阈值。
- `report.py`：Markdown、JSON、metrics CSV及本地图表。
- `simulator.py`：正常、噪声、CRC、超时和断线异常注入。

固件协议v1未提供MCU/IMU名称、WHO_AM_I、任务栈/堆及校准偏差等查询字段。CLI对这些字段输出`NOT_AVAILABLE`，不以0或主机常量代替设备响应。

## 安装与测试

```powershell
python -m pip install -e .\host
powershell -ExecutionPolicy Bypass -File .\tools\check-phase6.ps1
powershell -ExecutionPolicy Bypass -File .\tools\test-phase6.ps1
```

模拟器、离线报告和真实串口验收在报告中分别标注，模拟结果不得写入`artifacts/phase06/final-validation`。

## 实机结果

2026-08-05在COM4（CH340，115200 8N1）完成真实设备验收：100个逻辑PING全部成功，
底层101次发送中1次瞬态超时由只读命令安全重试恢复。最终交互会话清空开始前串口积压后采集
60.0秒，共601个Motion帧和60个Health帧；平均10.0167 Hz，设备间隔固定100 ms，
sequence主导步长为+10，重复、回退、缺口、估算丢帧、主机CRC及Parser错误均为0。
Roll范围为-27.04°～33.35°，Pitch范围为-40.58°～25.81°，平均加速度模长
1001.75 mg。串口关闭1秒后重新打开并PING成功。

为保证主机命令链路可恢复，固件BSP最小补充了STM32F1 UART错误标志清除与接收重挂载，
命令响应和周期遥测改用独立固定发送缓冲区；未增加RTOS任务、动态内存或UART DMA。
