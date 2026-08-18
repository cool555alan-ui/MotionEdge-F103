# 5 分钟实机演示脚本

> 前提：固件为 v1.0.1，串口示例使用 `COM4`，Broker/Node-RED 已按项目配置启动。SG90 与 MPU6500 机械独立；舵机只演示“姿态输入 → PD 计算 → 反方向执行器响应”，不会带动传感器。

| 时间 | 操作与命令 | 预期现象 | 失败时检查 |
|---|---|---|---|
| 0:00 | 1. 上电，确认 STM32、MPU6500、SG90 和串口连接。 | 板卡正常启动，舵机保持未授权安全状态。 | 检查 5 V 舵机电源、共地、串口方向；不要反复热插传感器。 |
| 0:20 | 2. `python -m motionctl doctor --port COM4` | 输出设备信息、状态和配置，通信诊断通过。 | 运行 `python -m motionctl ports`，确认端口未被串口工具占用。 |
| 0:40 | 3. `python -m motionctl monitor --port COM4 --duration 15` | 持续显示 Roll/Pitch 与健康遥测。 | 确认 MPU6500 在线、I2C 接线和供电稳定。 |
| 1:05 | 4. 手持传感器缓慢改变 Roll/Pitch。 | 数值方向连续、回零稳定，无明显跳变。 | 放慢动作并避开强振动；先核对坐标轴定义。 |
| 1:25 | 5. 查看 Node-RED 仪表/曲线。 | Roll/Pitch 曲线与手持动作同步，约 10 Hz 更新。 | 检查 Gateway、Broker、topic 和 Node-RED flow 是否在线。 |
| 1:50 | 6. `python -m motionctl actuator arm --port COM4` | 执行器获得显式授权，但仍在安全窗口内。 | 检查舵机独立供电与共地；用 `actuator status` 查看状态。 |
| 2:10 | 7. `python -m motionctl control pid set --port COM4 --kp 1.0 --ki 0 --kd 0.05 --output-limit-us 10 --derivative-alpha 0.2`，随后 `python -m motionctl control enable --port COM4 --axis pitch` | 控制状态为 Pitch、PD 参数生效。 | 用 `control pid get` 和 `control status` 读回；不要扩大 PWM 范围。 |
| 2:40 | 8. 缓慢正负改变 Pitch。 | SG90 随姿态作约定的反方向响应；传感器仍由手持控制，舵机不带动 MPU6500。 | 检查 direction、axis、Arm 状态、姿态新鲜度和 1450–1550 µs 约束。 |
| 3:20 | 9. 在 Node-RED/MQTT 下发一次允许的 PID 配置，再读回。 | 参数经网关到设备并返回结果，曲线继续更新。 | 检查命令 ID、非 retained、Broker 连接及网关日志；实时控制应仍在本地继续。 |
| 4:05 | 10. `python -m motionctl control estop --port COM4` | 控制立即禁止，舵机停止受 PID 驱动。 | 若状态未更新，直接断开舵机独立电源，并检查串口和设备状态。 |
| 4:30 | 11. `python -m motionctl actuator disarm --port COM4`，再读取 `control status` 与 `actuator status`。 | 最终为 control disabled、actuator disarmed 的安全状态。 | 不结束演示，直到状态读回安全；必要时关闭舵机电源。 |

## 讲解主线

一句话串联演示：“MPU6500 感知姿态，STM32 在 100 Hz 本地完成融合和 PD 控制，SG90 以反方向动作呈现控制输出，MQTT/Node-RED 负责 10 Hz 可视化和受控参数配置；网络不进入实时控制必经路径。”
