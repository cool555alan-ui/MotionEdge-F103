# 从复试老师视角评审 MotionEdge-F103

## 项目亮点

1. 链路完整：从驱动、算法、RTOS、协议到 IoT、Flash 和 CI，不是孤立 Demo。
2. 边界意识：主动区分姿态驱动控制与机械反馈闭环，MAE 和 PWM 统计均有限定语。
3. 实时设计可解释：四任务频率有理由，PID 不额外建任务，静态资源可审计。
4. 安全语义明确：Arm、Owner、Timeout、Clamp、ESTOP 和安全启动逐项可查。
5. Evidence 完整：Summary/CSV/Figure/Commit/Release 可以回答“数字怎么来的”。

## 一般部分

- 互补滤波和 SG90 本身并不新颖；价值来自参数选择、验证和系统集成。
- Node-RED 更像工程展示层，不应当作为算法创新点。
- 600 s 是有用的阶段门禁，但不是长期可靠性研究。

## 最容易被质疑的部分

1. `0.352°` 是否可信：必须先说 iPhone 参考和 `REFERENCE_LIMITED`。
2. 为什么称 PID：完整模块支持 PID，但当前对象最终采用 Ki=0 的 PD 配置。
3. 是否闭环：项目没有机械外环，只能说姿态输入驱动和执行器安全控制链。
4. `54.4%` 是什么：PWM 输出标准差的两次人工输入对比，不是超调或机械抖动。
5. `2 ms` 与 `216.58 ms`：前者是本地 telemetry 接收段，后者是 command RTT。

## 高风险表述

- “高精度”“工业级”“自平衡”“云端实时闭环”“永久零丢包”都会降低可信度。
- “五重保护”不如逐项解释 Arm/Owner/Timeout/Clamp/ESTOP。
- “PID 让舵机更稳 54.4%”缺少物理测量对象；应说 PWM output standard deviation。

## 最值得继续追问的技术

- Parser 如何从半帧/错帧恢复，CRC 与安全的边界。
- Queue/Mutex/Event Flag 的语义选择和固定资源预算。
- Ki=0、D 滤波、deadband 和 output limit 与对象边界的关系。
- 双槽事务中 CRC、commit marker、generation 各自解决什么。
- Broker 掉线时本地 PID 为什么仍连续，系统的实时边界在哪里。

## 总体评价

这是一个“工程完整度高于单点算法新颖度”的学生项目。最佳展示策略是先讲清系统边界，再用三条证据链支撑：100 Hz 本地姿态/控制、协议到 IoT 的可观测性、双槽 Flash 与 CI 的可靠性。若答辩中克制指标外推并能沿代码定位设计决定，项目说服力较强。
