# MotionEdge-F103 数字速查卡

| 数字 | 代表什么 |
|---:|---|
| 100 Hz | MPU6500 姿态更新与 MCU 本地控制频率 |
| 500 samples | 上电静态零偏校准样本数，约 5 s |
| 0.20 | 加速度低通 alpha |
| 0.98 | 互补滤波陀螺仪权重；加速度计权重 0.02 |
| 0.352° | Roll MAE，iPhone 参考，`REFERENCE_LIMITED` |
| 0.375° | Pitch MAE，iPhone 参考，`REFERENCE_LIMITED` |
| 0.019° | Roll 600 s 静态标准差 |
| 0.016° | Pitch 600 s 静态标准差 |
| 1450 / 1500 / 1550 µs | SG90 绝对安全最小/中心/最大 PWM |
| 1.0 / 0 / 0.05 | 最终 Kp/Ki/Kd；完整 PID 模块的 PD 配置 |
| 5.555 → 2.535 µs | P-only → PD 的 PWM 输出标准差 |
| 54.4% | 上述 PWM 输出标准差下降，不是总体性能或机械抖动 |
| 4934 / 4934 | Phase 7 稳定窗口 Gateway / Node-RED Motion |
| 2 ms | Gateway → Node-RED 本地 P95，不是命令 RTT |
| 2.80 s | Phase 7 Broker recovery |
| 624.742 s | v1.0 最终综合实机验收时长 |
| 59240 B | v1.0.1 Debug Flash 使用量 |
| 3068 B saved | 相对 v1.0.0 的 Debug Flash 节省量 |

边界口令：单 MPU6500 手持输入；SG90 不改变传感器姿态；不是外部机械闭环。完整来源见 [`../PROJECT_METRICS.md`](../PROJECT_METRICS.md)。
