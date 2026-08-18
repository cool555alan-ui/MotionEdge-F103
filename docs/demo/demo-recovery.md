# 演示故障恢复卡

每类故障最多执行下列 3–5 步；恢复后先确认安全状态，再继续演示。

## 找不到 COM 口

1. 运行 `python -m motionctl ports`。
2. 关闭可能占用端口的串口助手、IDE monitor 或旧 gateway。
3. 重新插拔 USB 串口并确认驱动，更新脚本中的 `COM4`。
4. 再运行 `doctor`，不要直接 Arm。

## ST-LINK 连接异常

1. P2 演示不需要重新烧录，优先继续使用已发布 v1.0.1。
2. 若设备本身未启动，检查 SWD、供电、BOOT0 和 NRST。
3. 关闭占用 ST-LINK 的调试会话后重连。
4. 仍失败则切换到备用已烧录板，不在现场修改固件。

## MPU6500 offline

1. 立即 ESTOP/Disarm，避免无新鲜姿态时驱动。
2. 断电检查 3.3 V、GND、SCL、SDA 与地址选择。
3. 重新上电后运行 `doctor` 和短时 `monitor`。
4. 只有姿态连续正常后才重新 Arm。

## Broker 不在线

1. 保持本地控制安全运行，不把网络故障当成本地控制故障。
2. 检查 Broker 进程、端口和 `config/motionedge-gateway.toml`。
3. 重启 Broker，再查看 gateway 自动重连日志。
4. 等待状态/遥测恢复后继续云端步骤。

## Gateway 异常

1. 关闭旧 gateway，确认串口没有被重复占用。
2. 运行 `python -m motionctl gateway run --config config/motionedge-gateway.toml`。
3. 查看串口、Broker、topic 和命令响应日志。
4. Gateway 未恢复时只展示本地 `monitor`，不要绕过安全命令。

## Node-RED 无数据

1. 先确认 Broker 上已有 motion/health 消息。
2. 检查 Node-RED flow 已部署且 topic 与 device ID 一致。
3. 刷新仪表页并检查 debug 节点。
4. 若仍无数据，用 CLI 展示本地姿态并说明显示链故障不影响本地控制。

## 舵机不动作

1. 查看 `actuator status` 和 `control status`，确认已 Arm、控制已 Enable、姿态新鲜。
2. 检查舵机 5 V 独立供电、共地和 PWM 引脚。
3. 执行 `actuator center` 验证基础执行器路径。
4. 恢复后重新设置 Pitch/PD；不扩大 PWM 窗口。

## PWM 触及安全边界

1. 立即执行 `control estop`，随后 Disarm。
2. 确认输出限制仍为 ±10 µs、绝对窗口为 1450–1550 µs。
3. 检查姿态零点、方向与 PID 参数读回。
4. 从中心位和小幅缓慢动作重新开始；不得现场扩窗。
