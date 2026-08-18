# MotionEdge-F103 技术亮点

## 1. 100 Hz 嵌入式姿态链

问题：六轴 IMU 的加速度计动态噪声与陀螺仪积分漂移不能单独满足稳定姿态显示。设计：在 STM32F103 上完成 500 样本校准、低通与互补融合，以 100 Hz 输出 Roll/Pitch。结果：静态标准差为 Roll 0.019°、Pitch 0.016°；相对手机参考的 MAE 为 0.352°/0.375°，但明确标为 `REFERENCE_LIMITED`。

## 2. 有边界的 FreeRTOS 实时架构

问题：采样、串口、遥测和健康监控频率不同，单循环容易互相阻塞。设计：拆分四个静态任务，使用固定队列、互斥快照和事件标志；PID 直接跟随 SensorTask，不新增 ControlTask。结果：历史代表实测为 100.003/500.012/10.001/1.000 Hz，独立 600 s 记录通过。

## 3. 100 Hz 姿态驱动执行控制

问题：手持姿态输入既要产生可见响应，又必须避免噪声和不受控输出。设计：完整 PID 模块叠加 1.0° 死区、D 项滤波、±10 µs 输出限制及执行器安全状态机，最终选择 Ki=0 的 PD 配置。结果：人工输入对比中 PWM 输出标准差由 5.555 µs 降至 2.535 µs，下降 54.4%；不将该指标解释为机械闭环性能。

## 4. Binary Protocol → Python → MQTT → Node-RED

问题：实时 MCU 不适合直接承担网络栈和 UI。设计：STM32 使用 CRC16 二进制协议，Python Gateway 完成串口到 MQTT 的边缘适配，Node-RED 负责波形、状态和低频配置。结果：Phase 7 稳定窗口 Gateway/Node-RED 为 4934/4934，Gateway → Node-RED 本地 P95 为 2 ms，Broker 恢复 2.80 s。

## 5. 双槽 Flash + CI + Release

问题：配置写入中断、错误版本和危险状态恢复会破坏可演示性与安全性。设计：双槽记录包含 Schema 1、CRC、generation 和最后写入的 commit marker；Arm/Owner/PID Enable 不持久化，并用 CI 固化测试、构建和资源门禁。结果：真实掉电、槽切换、Factory Reset、安全启动通过；v1.0.1 在不缩 Stack/Queue/Buffer 的情况下节省 3068 B Debug Flash。
