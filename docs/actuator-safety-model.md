# 执行器安全模型

## 状态与控制权

上电固定进入 `DISABLED/NONE`，不会恢复上次动作。Arm 后进入 `MANUAL`，Owner 只能是 LOCAL、SERIAL、MQTT 或 CONTROL_LOOP 中的一个。串口与 MQTT 不得抢占对方；Disarm 和 ESTOP 属于安全动作，允许解除现有控制。

当前 Phase 9A 不暴露 `ATTITUDE_HOLD` 启用命令。传感器异常时允许已 Arm 的安全手动控制继续；未来自动模式遇到传感器离线或 MotionFrame 过期必须退出。App 进入 FAULT 时，所有模式立即停止 PWM。

## 边界

- 角度使用 0.01° 有符号整数，初始软件窗口为 -45°～+45°。
- PWM 使用 µs 无符号整数，初始软件窗口为 1000～2000 µs。
- 斜率默认 500 µs/s，更新周期 10 ms，超大 `dt` 限制为 100 ms，时间差采用无符号回绕安全计算。
- 手动命令 1000 ms 未刷新时，目标自动回到 1500 µs；旧目标不会无限保持。
- ESTOP 当前采用方案 B：立即停止 PWM、清除 Owner、要求重新 Arm。实机机械结构确认前不假设断 PWM 后仍安全保持。
- retained MQTT 命令和过期命令被拒绝；重复 request_id 返回缓存结果，不重复执行动作。

没有电流检测硬件，因此 `overcurrent=NOT_AVAILABLE`。PID、自动闭环、自动重新 Arm 和 MQTT 实时闭环均不在 Phase 9A 范围内。
