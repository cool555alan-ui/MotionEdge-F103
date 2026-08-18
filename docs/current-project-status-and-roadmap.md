# MotionEdge-F103 当前状态与后续路线

更新时间：2026-08-18。固件发布基线为 **v1.0.1**；P2 只整理展示、技术文档和复试材料，不修改固件行为。

## 项目定义

MotionEdge-F103 是“基于 STM32 的姿态感知与物联网控制平台”：STM32F103C8T6 以 100 Hz 读取 MPU6500 并计算 Roll/Pitch，在本地执行姿态驱动的 PD 舵机控制；Python Gateway、MQTT 与 Node-RED 负责 10 Hz 数据展示和受控参数配置。

控制链为：

`MPU6500 姿态感知 → 互补滤波 → 相对零位误差 → PD 计算 → 安全限幅 → SG90 输出`

SG90 与 MPU6500 **机械独立**，不会调整传感器位置。因此它不是自平衡系统或外部机械姿态闭环；准确表述是“PID-based attitude-driven servo control（姿态感知 → PID 控制计算 → 执行器输出控制链）”。控制器支持 P/I/D，最终实测配置为 **Kp=1.0、Ki=0、Kd=0.05**，即 PD。

## 已完成状态

| 能力 | 状态 | 可核查事实 |
|---|---|---|
| MPU6500 与姿态 | PASS / REFERENCE_LIMITED | 100 Hz；有限 iPhone 参考下 Roll/Pitch MAE 为 0.352°/0.375°，不代表绝对精度 |
| FreeRTOS | PASS | 100/500/10/1 Hz 四条任务路径；独立 600 s soak 无栈溢出和 malloc failure |
| 姿态驱动舵机控制 | PASS_WITH_WARNINGS | Pitch、Kp=1.0、Ki=0、Kd=0.05；1450–1550 µs 安全窗；PWM 标准差降低 54.4%，输入为人工有限轨迹 |
| MQTT/Node-RED | PASS | 稳定区间 4934/4934 帧，观测丢失 0；同机 P95 2 ms；Broker 约 2.80 s 恢复 |
| 配置持久化 | PASS | Schema 1、2048 B 保留区、真实断电恢复与 FakeFlash 故障注入通过 |
| 系统终验 | PASS_WITH_WARNINGS | 624.742 s，无复位、Fault、控制失败或数据链失败；Sensor deadline 增量 1 |
| v1.0.1 资源 | PASS | Debug Flash 59240 B、RAM 17824 B；相对 v1.0.0 Debug Flash 减少 3068 B |

指标、证据和限制分别见 [项目指标事实源](PROJECT_METRICS.md)、[证据索引](EVIDENCE_INDEX.md) 与 [面试限制清单](interview/limitations.md)。

## 当前文档工程

- [README](../README.md)：项目入口、核心能力、指标、运行和安全边界。
- [架构说明](architecture.md)：分层、实时数据流、边云路径和安全状态机。
- [技术报告](MotionEdge-F103-technical-report.md)：从需求、设计取舍到验证和局限。
- [代码导览](code-tour.md)：按 10 个停靠点理解工程。
- [面试材料](interview/qa-bank.md)：1/3/10 分钟介绍、60 题问答和追问链。
- [演示脚本](demo/demo-script.md)：5 分钟安全演示及恢复卡。
- [简历描述](resume/project-description.md)：姿态控制、RTOS、边云三种版本。

## 后续优化阶段

1. **P3：可追溯姿态标定。** 使用标定转台或可追溯角度基准，扩大角度、温度和动态范围，建立不确定度预算，解除 REFERENCE_LIMITED。
2. **P4：机械闭环原型。** 仅在舵机真正带动 IMU 所在平台后，重新建立对象模型、辨识参数并验证超调、调节时间和稳态误差。
3. **P5：产品化通信。** 在保持本地实时控制的前提下增加认证、TLS、ACL、协议模糊测试和公网环境测试。
4. **P6：硬件可靠性。** 增加电流/电压监测、独立硬件急停、机械限位、EMI/温漂和长时寿命验证。

## 冻结规则

P2 不建立 v1.0.2，不重跑硬件长测，也不调整协议、RTOS、PID 或执行器范围。任何后续代码优化都应从独立版本开始，并先定义可复现验收标准。
