# Phase 9B 基于PID的姿态交互式舵机控制

## Control Interpretation and Limitations

1. 当前系统只有一个MPU6500。
2. MPU6500测量用户手持面包板输入的Roll或Pitch。
3. SG90运动不会反向改变该MPU6500姿态，因此不存在外部姿态机械反馈环。
4. PID真实运行于STM32 SensorTask的100 Hz新MotionFrame路径，并动态调节SG90 PWM。
5. SG90内部具有自身位置反馈，但其机械角度没有被本项目外部测量。
6. 本实现称为`PID-based attitude-driven servo control`，不是自平衡、姿态稳定平台或外部姿态闭环。
7. 不报告不存在的Plant调节时间、超调量或稳态控制误差；人工动态输入标记为`HUMAN_INPUT_LIMITED`。
8. iPhone水平仪仅为`REFERENCE_LIMITED`辅助参考。

## 实时路径与单位

`MPU6500 → MotionService → SensorTask 100 Hz → ControlService → PidController → ActuatorService → TIM3_CH1/PA6 → SG90`

进入PID模式时捕获所选轴当前姿态作为相对零位，等待5个新鲜样本后激活。误差以degree输入PID，Kp单位为µs/degree，Ki为µs/(degree·s)，Kd为µs/(degree/s)，输出为相对1500 µs的PWM偏移。D项采用负的measurement derivative并使用一阶滤波，避免设置零位造成Derivative Kick。

默认配置为Kp=1.0、Ki=0、Kd=0、Deadband=1.0°、D alpha=0.20、积分禁用、输出±10 µs。实机实验只能按±10→±20→±30→±50 µs逐级扩大，ActuatorService最终仍硬限制1450–1550 µs。

## 安全策略

Enable要求执行器已Arm、App RUNNING、传感器在线、已校准、Motion有效且新鲜。Sensor offline、Motion stale、Calibration失效、App Fault、Actuator Fault、ESTOP或非有限运算会退出PID、Reset控制器并停止执行器；恢复后不会自动重新Enable。普通Disable同样停止PWM并要求重新Arm。

积分默认禁用，因为持续手持倾角不是由执行器可消除的误差。通用PID仍支持bounded和leaky积分、积分限幅及conditional anti-windup，但只有有限实机假设验证后才允许非零Ki。

MQTT/Node-RED只执行低频配置和监控。Broker或Python网关断开不改变STM32本地100 Hz路径。所有副作用命令禁止自动重试、retained命令被拒绝，并继续使用request_id去重。
