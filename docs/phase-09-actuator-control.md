# Phase 9A PWM 执行器控制

Phase 9A 只实现安全 PWM 和开环舵机控制。系统上电后执行器为 `DISABLED`，TIM3 PWM 不启动；只有显式 `ARM` 才会在 PA6 输出 50 Hz PWM，并从 1500 µs 安全中位开始。

当前SG90实机验证范围为1400～1600 µs；正式软件窗口在两侧各留50 µs裕量后固化为1450/1500/1550 µs。该窗口是安全控制范围，不声明真实机械角度或机械极限。

## 架构

数据与控制路径如下：

`MPU6500 -> 姿态解算 -> FreeRTOS SensorTask(100 Hz) -> Actuator Safety -> TIM3_CH1/PA6 -> Servo`

执行器更新复用 SensorTask，不新增任务或任务栈。MQTT 和 Node-RED 仅用于管理与观测，不属于实时控制环。

## CubeMX 基线

- Timer：TIM3，Channel 1，PA6
- Timer 输入时钟：72 MHz（APB1=36 MHz，定时器倍频）
- Prescaler：71，计数频率 1 MHz，即 1 µs/count
- ARR：19999，周期 20,000 µs，即 50 Hz
- CubeMX 初始 CCR：1500；应用初始化不会启动 PWM
- HAL timebase：TIM4，与 PWM 隔离

## 软件分层

- `BSP/bsp_pwm.*`：HAL/TIM3、启停和 µs 到计数值换算。
- `Components/servo_actuator.*`：整数角度映射、限幅和斜率控制，不依赖 HAL/RTOS。
- `Services/actuator_service.*`：Arm、Owner、超时、ESTOP 和故障联锁。
- `motionctl actuator`：串口手动控制与逐步标定。

Phase 9B PID 未实现。只有舵机能真实改变 MPU6500 所在平台的一个明确姿态轴，并且 Phase 9A 实机核心项全部通过后，才允许增加闭环。
