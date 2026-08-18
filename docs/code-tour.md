# MotionEdge-F103 代码导览

老师如果要求“展示代码结构”，建议按下面 10 个核心文件阅读。每站只回答职责、关键接口和分层理由，不逐行翻代码。

## 1. `App/app_main.c`

- 职责：装配各 BSP、Service 和应用状态，提供 RTOS 调用的单次运行入口。
- 关键接口：`App_Init`、`App_SensorRunOnce`、`App_CommunicationRunOnce`、`App_TelemetryRunOnce`。
- 分层理由：初始化顺序和跨服务编排属于 Application，不放进 CubeMX `main.c` 或单个 Service。

## 2. `App/RTOS/rtos_tasks.c`

- 职责：创建四个静态任务，执行 100/~500/10/1 Hz 调度和运行监测。
- 关键点：`SensorTask` 同时触发 sampling、attitude、control；没有额外 ControlTask。
- 分层理由：RTOS 只管理节拍、队列、快照和事件，不包含算法公式或 HAL 操作。

## 3. `Services/sensor_service.c`

- 职责：管理 MPU6500 在线状态、采集时序和失败恢复。
- 关键接口：初始化、周期采样、状态/错误查询。
- 分层理由：Device 只表达寄存器访问，SensorService 才表达“设备是否可用于系统”。

## 4. `Services/motion_service.c`

- 职责：把原始六轴数据交给校准、低通和姿态估计，生成带 sequence、timestamp、valid/calibrated 标志的 MotionFrame。
- 关键接口：周期更新、`MotionService_GetLatestFrame`、运行时滤波参数设置。
- 分层理由：它连接多个纯算法组件，但不直接访问 HAL 或执行器。

## 5. `Algorithms/attitude_estimator.c`

- 职责：根据加速度计重力方向和陀螺仪积分计算 Roll/Pitch 互补融合。
- 关键接口：初始化、重置、按 `dt` 更新。
- 分层理由：纯数学模块无 STM32 依赖，可在 Host C 中测试边界、符号和非有限值。

## 6. `Algorithms/pid_controller.c`

- 职责：完整 P/I/D、D 项滤波、积分模式、anti-windup/限幅与状态复位。
- 关键接口：`PidController_Init`、`PidController_Reset`、`PidController_Update`。
- 分层理由：PID 不知道角度来自 MPU6500，也不知道输出最终是 PWM；单位与安全语义由 ControlService 负责。

## 7. `Services/control_service.c`

- 职责：选择 Roll/Pitch、建立相对零位、应用方向和死区、检查姿态新鲜度、调用 PID 并请求安全执行器输出。
- 关键接口：Enable/Disable、SetZero、SetAxis/Direction/PID/Deadband、Update、GetStatus。
- 分层理由：这是“姿态误差到受限执行请求”的业务层，不直接写 TIM3。

## 8. `Services/actuator_service.c`

- 职责：显式 Arm、Owner 仲裁、1450–1550 µs clamp、斜率/超时、ESTOP 和故障状态。
- 关键接口：Arm/Disarm/EmergencyStop、BeginAttitudeControl、SetTarget/GetStatus。
- 分层理由：无论命令来自串口、MQTT 或 ControlService，都必须经过同一安全状态机。

## 9. `Middleware/protocol_parser.c` + `Services/command_service.c`

- 职责：Parser 处理流式半帧、粘包、长度/版本/CRC 错误；CommandService 校验命令 payload、范围、状态和权限。
- 关键接口：逐字节/块输入 parser、命令分派与结构化响应。
- 分层理由：传输完整性与业务合法性分开，便于 fuzz/golden-vector 测试，也避免解析器直接操作硬件。

## 10. `Services/config_store.c` + `host/motionctl/gateway.py`

- ConfigStore：双槽 Schema 1、CRC、generation、commit marker 和安全默认值；BSP 负责真实 Flash。
- Gateway：独占串口，把设备模型映射到 MQTT topic，执行去重、过期和 retained 拒绝。
- 为什么放在最后：它们展示同一原则在设备端和主机端的应用——先冻结数据契约，再隔离存储/网络机制。

## 推荐现场路线

```text
app_main
  → rtos_tasks / SensorTask
  → sensor_service
  → motion_service
  → attitude_estimator
  → pid_controller
  → control_service
  → actuator_service
  → protocol_parser / command_service
  → config_store / gateway
```

对应架构图见 [`architecture.md`](architecture.md)，验证证据见 [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)。
