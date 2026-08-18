# MotionEdge-F103 技术报告

## 1. 项目背景

MotionEdge-F103 是“基于 STM32 的姿态感知与物联网控制平台”。项目选择 STM32F103C8T6、MPU6500 和 SG90，不是为了复现商品姿态稳定器，而是把嵌入式项目中经常分散出现的能力连成一条可以验证的工程链：传感器驱动、姿态估计、实时调度、控制算法、执行器安全、设备协议、Python 工具、MQTT 观测、Flash 持久化和持续集成。

系统的控制定义必须先说清楚。MPU6500 测量用户手持板姿态，PID 根据相对零位计算舵机 PWM；SG90 不会带动 MPU6500，所以系统没有“舵机输出 → 被控机构 → 同一传感器”的机械反馈边。本报告称其为 **PID-based attitude-driven servo control**，即“姿态感知 → PID 控制计算 → 执行器输出控制链”，不声称自平衡、外部机械姿态闭环或不存在的机械超调指标。

## 2. 系统需求与边界

项目需求分为五类：第一，稳定识别 MPU6500 并在 100 Hz 下输出 Roll/Pitch；第二，用 FreeRTOS 隔离不同频率的采集、通信、遥测和健康工作；第三，在 MCU 本地执行受限 PID 控制和执行器安全状态机；第四，用二进制协议、Python Gateway、MQTT 和 Node-RED 完成低频配置及实时观测；第五，用双槽 Flash、主机测试、CI 和 Release 形成可追溯工程闭环。

约束同样重要：MCU 物理 Flash 64 KiB，配置区固定占用末尾 2048 B；固件禁止动态内存；HAL 只在 BSP/驱动层；舵机必须独立稳压 5 V 并与 STM32 共地；MQTT 当前为本地无 TLS 原型；Phase 8 的手机水平仪参考属于 `REFERENCE_LIMITED`。

## 3. 硬件组成

主控是 STM32F103C8T6。MPU6500 通过 I²C1 PB6/PB7 接入，地址 `0x68`，`WHO_AM_I=0x70`；USART1 PA9/PA10 以 115200 bit/s 连接 CH340；SG90 信号连接 TIM3_CH1 PA6，50 Hz。ST-LINK 用于 SWD 下载与调试。

SG90 供电与数字系统分开考虑：舵机使用独立稳压 5 V，信号地与 STM32 共地。这样做的理由不是追求复杂供电，而是降低舵机启动电流和反电动势对 MCU、I²C 与串口稳定性的影响。执行器测试使用无负载和无遮挡条件，现场演示也不做堵转或极限搜索。

外设初始化来自 STM32CubeMX，用户业务代码不写在自动生成区。`BSP/bsp_i2c.c`、`bsp_uart.c`、`bsp_pwm.c`、`bsp_flash.c` 封装 HAL；`Devices/mpu6500.c` 只通过 BSP 接口实现芯片寄存器语义。这使算法和 Service 能在主机环境中测试。

## 4. Firmware 分层

结构由下到上为：HAL/Hardware → BSP/Devices/Middleware → Algorithms/Components → Services → Application/RTOS，详见 [`architecture.md`](architecture.md)。分层的核心不是目录整齐，而是让变化边界清晰：更换 I²C 实现不修改姿态算法；改变 MQTT 展示不进入实时控制；协议解析错误不直接操作 PWM。

`App/app_main.c` 负责初始化顺序和单次业务入口；`App/RTOS/rtos_tasks.c` 负责周期调用。`Services/` 中的 Sensor、Motion、Control、Actuator、Communication、Config 和 Health 服务分别拥有状态；`Algorithms/` 中的低通、姿态与 PID 不依赖 HAL。代码导览见 [`code-tour.md`](code-tour.md)。

## 5. MPU6500 采集

启动时先验证 I²C 地址和身份寄存器，再进行唤醒与配置。采集路径不会把“读到字节”直接等同于有效姿态：驱动返回状态、样本范围、时间戳和 stale 标志均进入上层判断。传感器离线或新鲜度超时会阻止/停止控制。

100 Hz 是本项目在动态响应、I²C 开销、F103 算力和任务调度之间的折中。10 ms 周期足以让手持姿态和 SG90 演示连续，又不必提高通信与 UI 频率。它不是 MPU6500 的硬件极限，也不暗示所有应用都应该选 100 Hz。

## 6. 静态校准

启动阶段收集 500 samples 估计静止零偏。样本数的意义是用约 5 s 时间平均降低随机噪声，同时保持上电等待可接受；校准要求静止，若输入不满足条件，更多样本也不会自动消除系统误差。

校准状态通过 Service 和事件标志向控制、协议与 UI 暴露。未校准样本不能进入 PID Enable 条件。这样把“算法已有输出”和“系统允许驱动执行器”分开，避免启动瞬态触发舵机。

## 7. 姿态融合

加速度计能提供重力方向，长期不积分漂移，但运动时会混入线加速度和高频噪声；陀螺仪短期响应快，但角速度积分会随零偏累积。项目先用 alpha `0.20` 的低通抑制加速度计高频变化，再使用 gyro weight `0.98` 的互补滤波：短期主要相信陀螺仪，低频由加速度计拉回。

最终只输出 Roll/Pitch。六轴 IMU 没有磁力计或其他航向绝对参考，静止时重力也不能约束绕重力轴的 Yaw，因此不制造绝对 Yaw 能力。若未来需要长期航向，应加入磁力计、视觉或其他外部参考，并重新处理磁干扰与标定。

Phase 8 的静态比较得到 Roll/Pitch MAE `0.352°/0.375°`、R² `0.99888/0.99937`；静态标准差为 `0.019°/0.016°`，30 min 漂移为 `-0.0099°/-0.0307°`。前两类依赖 iPhone 内置水平仪，其不确定度未知，因此必须标记 `REFERENCE_LIMITED`，不能改写为绝对精度。

## 8. FreeRTOS 设计

系统使用四个静态任务：SensorTask 100 Hz，CommunicationTask ~500 Hz，TelemetryTask 10 Hz，HealthTask 1 Hz。不同任务对应不同时间语义：传感与控制需要固定节拍；串口解析需要快速服务；遥测无需占用 100 Hz 网络带宽；健康统计适合低频聚合。

SensorTask 同时执行 sampling、attitude 和 control。没有额外创建 ControlTask，因为控制必须消费同一周期的新姿态；拆成新任务会增加任务栈、上下文切换、同步对象和相位不确定性。CommunicationTask 约 2 ms 调度一次，避免串口 backlog，但它不表示协议或网络必然具有 2 ms 延迟。

任务间使用固定大小 command queue、受互斥保护的 motion snapshot 和 event flags。Queue 表达有顺序的命令交接；Mutex 保护一致快照而不丢覆盖；Event Flag 广播 ready、calibrated、fault 等状态。历史代表实测频率为 100.003、500.012、10.001、1.000 Hz；独立 600 s 验证中 Stack Overflow 和 Malloc Failure 均为 0。数字只代表对应运行，不是所有版本恒定值。

v1.0 最终系统验收持续 624.742 s。Sensor deadline delta 为 1，其他任务为 0；单次 miss 未伴随 reset、fault、数据损坏或控制失败，因此最终结果保留 warning，而不是隐藏或扩大解释。

## 9. Binary Protocol

STM32 与 Python 之间采用 Binary Protocol v1，而不是串口 JSON。二进制帧固定版本、类型、标志、sequence、payload length 和 CRC16-CCITT-FALSE，减少 F103 的解析、字符串和缓冲开销，并便于对半帧、粘包、噪声、错长和 CRC 错误做确定性恢复。

`Middleware/protocol_parser.c` 是流式状态机：数据可以分段到达；非法长度、版本或 CRC 会计数并重新寻找帧边界。`Services/command_service.c` 再做命令 ID、payload 长度、范围、设备状态和权限校验。协议层只确认帧完整，Service 层决定动作是否安全。

CRC16 用于发现传输错误，不提供认证或加密。若系统暴露到不可信网络，需要在 MQTT/部署层加入 TLS、身份认证和 ACL，不能把 CRC 当安全机制。

## 10. PID 与执行器安全

`Algorithms/pid_controller.c` 完整支持 P/I/D、D 项滤波、积分模式和输出限制。最终运行参数为 Pitch、Kp `1.0`、Ki `0`、Kd `0.05`、D filter alpha `0.2`、Deadband `1.0°`、output limit `±10 µs`。

Ki=0 不是因为没有实现积分，而是控制对象边界决定的。当前是手持姿态到舵机位置的映射，舵机输出不会减少 MPU6500 的姿态误差；如果用户持续保持 10° 输入，普通积分会持续累积并把输出推向限幅。最终 PD 配置保留比例映射和变化率抑制，更符合当前演示语义。若未来形成真实机械外环，再依据稳态误差、执行器饱和和抗积分饱和重新启用 Ki。

D 项对测量噪声敏感，因此采用 alpha `0.2` 滤波。相较纯 P 实验，PD 配置下 PWM 输出标准差由 `5.555 µs` 降至 `2.535 µs`：

```text
(5.555 - 2.535) / 5.555 ≈ 54.4%
```

这是 `HUMAN_INPUT_LIMITED` 的 PWM output standard deviation reduction，不是舵机电气抖动、机构超调或总体控制性能提升。

安全边界由 `ActuatorService` 独立执行：1450 / 1500 / 1550 µs 绝对窗口、显式 Arm、单一 Owner、command timeout、斜率限制和 ESTOP。ControlService 只能在 App Running、Sensor Online、样本有效且已校准、姿态未过期、执行器已 Arm 时 Enable。异常进入中心/停机路径；MQTT 不能绕过安全状态机。

## 11. Python、MQTT 与 Node-RED

`motionctl` 提供端口发现、doctor、命令、采集、验证和报告。Gateway 独占串口，把二进制设备模型转为 MQTT JSON；Node-RED 展示 Roll/Pitch、控制项和状态，并提供低频配置入口。100 Hz PID 不经过 Python 或 Broker，因此 Gateway/Broker 掉线不改变本地控制节拍。

MQTT 命令采用非 retained 消息，包含过期时间和 `request_id`；重复请求使用有限缓存拒绝重复执行。QoS 1 允许 Broker 确认送达，但可能重复，所以必须和幂等/去重一起设计。retained 控制命令被拒绝，避免设备重连后执行旧 Arm 或动作。

Phase 7 稳定窗口 Gateway/Node-RED Motion 为 `4934/4934`，loss 0；Gateway → Node-RED local P95 为 `2 ms`，Broker recovery 为 `2.80 s`。PING command round-trip P95 是 `216.58 ms`，它包含命令排队、串口请求响应等路径，不能写成遥测延迟。v1.0 最终验收的 Node-RED local P95/max 为 1 ms/2 ms，Broker interruption 为 27.068 s，期间本地 PID 连续。

## 12. 双槽 Flash Persistence

配置区固定为 `0x0800F800–0x0800FFFF`，共 2048 B，分为两个 1 KiB Slot；Record 54 B，Schema 1。写入新 generation 时选择目标槽、擦除、写 header/payload/CRC，最后写 commit marker。CRC 检测内容损坏；commit marker 区分完整提交和掉电半写；generation 在两个有效槽之间选更新记录，三者职责不同。

真实断电验证覆盖保存值恢复、未保存 RAM-only 变更丢弃、A/B 槽切换、Factory Reset 和 Safe Boot。FakeFlash 覆盖 erase/program/verify 失败、partial record、CRC 损坏和双槽无效回退；它是软件故障注入，不冒充物理掉电注入。

Firmware Version 与 Config Schema 分开。版本描述整套软件发布，Schema 只描述 Flash record 兼容性；补丁版本不必改变配置格式。上电永不恢复 Arm、Owner、PID Enable，安全状态保持 Control Disabled、Actuator Disarmed、Owner NONE、PWM `1500 µs`。

## 13. CI、Release 与资源

CI 使用固定 Arm GNU Toolchain 14.2.Rel1，执行 Host C、Python、Debug/Release、size/overlap 和 release gate。配置区从应用 Flash 上限中扣除，不能把 F103C8 假定成 128 KiB，也不能让镜像进入 `0x0800F800`。

v1.0.0 Debug 为 62308 B Flash、17832 B RAM；Release 为 54296 B/17824 B。v1.0.1 只对稳定 HAL/FreeRTOS Debug 目标使用 `-Os`，应用保持 `-Og -g3`，得到 Debug `59240 B`、RAM `17824 B`，Flash 节省 `3068 B`、剩余 `4248 B`；Release 仍为 54296 B/17824 B。没有缩 Task Stack、Queue、Buffer 或安全逻辑，没有使用 LTO 换取数字。

Release 包含 ELF/HEX/BIN、Python wheel/sdist、Gateway 示例、Node-RED flow、manifest、说明和 SHA-256。版本统一为 1.0.1，Config Schema 保持 1。

## 14. 实验方法

测试按风险分层：纯算法和协议在 Host C/Python 中重复执行；传感、RTOS、执行器、掉电和系统链路使用真实硬件；网络通过本地 Mosquitto/Node-RED 验证；无法安全自动化的人工姿态输入显式标记 `HUMAN_INPUT_LIMITED`。原始 CSV、Summary JSON、Report 和 Figure 通过 [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) 追溯。

长测不等同于同一件事：RTOS 600 s 看调度、连续性与 fatal hook；Phase 7 600 s 看 MQTT 稳定窗口；Phase 8 1800 s 看静态漂移；Phase 9B 600 s 看控制安全；Phase 10 624.742 s 看综合链路。P2 只整理既有 evidence，没有重新运行硬件。

## 15. 结果摘要

系统实现了从 MPU6500 到 Roll/Pitch、从姿态到安全 PWM、从二进制协议到本地 IoT、从运行时配置到双槽 Flash 的完整工程链。价值不在单个 MAE 或延迟数字，而在每个数字都有测试类型、限制和原始路径，并且失败模式有安全状态。

关键结果：100 Hz 姿态与控制；`REFERENCE_LIMITED` Roll/Pitch MAE 0.352°/0.375°；PWM 输出标准差 5.555 → 2.535 µs（54.4%）；MQTT 稳定窗口 4934/4934、local P95 2 ms；真实掉电持久化 PASS；v1.0.1 Debug Flash 59240 B，节省 3068 B。

## 16. Limitations

1. 单 IMU 不构成机械外环，机构超调、调节时间、稳态误差不适用。
2. 六轴 IMU 无绝对 Yaw 参考。
3. iPhone 水平仪参考不确定度未知，姿态 MAE 为 `REFERENCE_LIMITED`。
4. PWM electrical jitter `NOT_TESTED`，Servo current telemetry `NOT_AVAILABLE`。
5. 本地 MQTT 无 TLS，不能直接公网部署。
6. 600 s/1800 s 是阶段验证，不是工业寿命、环境或 EMC 认证。
7. F103C8 RAM 余量 1120 B，继续扩展网络栈或缓存前必须重新预算。

## 17. Future Work

只保留与当前边界直接相关的四项：

1. 搭建单轴机械反馈平台，让 SG90 实际改变被测机构姿态，再讨论真正的机构反馈控制指标。
2. 加入编码器或第二 IMU，区分执行器角度、平台姿态与手持命令输入。
3. 若需要更复杂算法、缓冲或网络安全，迁移到更高资源 MCU，而不是压缩现有安全余量。
4. 公网部署前增加 TLS、设备身份、ACL、证书轮换与威胁模型。

项目主体固件冻结在 v1.0.1；以上是后续研究方向，不是当前已实现能力。
