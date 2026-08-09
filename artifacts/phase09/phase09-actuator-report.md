# MotionEdge Phase 9 执行器验收报告

- 验证日期：2026-08-09
- 固件基线提交：`ad4410fae0eb9f2aa1c871ca81dd3b102f47475b`（Phase 9 工作区尚未提交）
- 固件/Python版本：`0.9.0` / `0.9.0`
- 硬件：STM32F103C8T6、MPU6500、SG90；舵机使用稳定外部5 V供电并与MCU共地
- 调试链路：ST-LINK `37FF71064E573436F8051F43`，V2J37S7，3.33 V，Device ID `0x410`
- 串口：CH340 `COM4`，115200 8N1，无流控

## Phase 9A：PWM与执行器安全控制

CubeMX配置TIM3_CH1输出到PA6。定时器输入72 MHz，PSC=71、ARR=19999，配置频率50 Hz，计数分辨率1 us；TIM4继续作为HAL timebase。真实电气波形周期与抖动因无示波器或逻辑分析仪标为NOT_TESTED，不使用CCR寄存器冒充波形测量。

更换稳定的外部5 V电源并共地后，SG90在1400、1450、1500、1550、1600 us五点均完成真实动作。1450和1550的位移较小，但用户确认不是卡死、持续抖动或异常失控。因此将1400–1600 us记录为本次测得的保守动作包络；正式软件窗口在两侧各保留50 us裕量，设为1450/1500/1550 us。该结果不是机械极限，也没有外部角度仪器测量，不用于声称绝对舵机角度准确。

重新构建、烧录和复位后，设备首次状态为DISABLED、owner NONE、armed=false，读回安全窗口1450–1550 us。实机发送诊断命令2000 us后，target/current均钳位至1550 us，limit_count由0增至1、fault_count保持0；随后ESTOP使设备恢复DISABLED、owner NONE、armed=false。

未Arm拒绝、命令超时回中心、ESTOP、App FAULT联锁、Owner冲突和Slew均已由实机或C主机测试覆盖。600秒中心位耐久期间，直接统计运动/执行器/健康帧4711/4711/452，应用未进入FAULT，执行器fault=0、timeout=0，UART/CRC/parser增量均为0。四任务deadline增量0/0/0/0；最小栈余量448/576/168/488 B，当前/历史最小堆3064/2440 B。

真实Broker测试验证retained执行器命令被拒绝、重复request_id只执行一次。Node-RED连续段52帧，gap、duplicate、JSON和schema错误均为0，本机延迟P95为1 ms。

Phase 9A结论：PASS。

## Phase 9B：真实姿态闭环

NOT_TESTED。尚未证明舵机能真实驱动MPU6500所在平台形成单轴Roll或Pitch机械闭环；未加入PID，也没有阶跃、超调、调节时间、稳态误差或扰动恢复数据。当前只能进入Phase 9B，不能进入Phase 10。

## 工程回归

- C主机断言：539/539 PASS
- Python：113/113 PASS
- Phase 1–9检查：PASS
- Debug：0 warning，Flash 51,920 B（79.22%），RAM 17,160 B（83.79%）
- Release：0 warning，Flash 45,628 B（69.62%），RAM 17,160 B（83.79%）
- `git diff --check`：PASS

## 证据

- `flash-log.txt`：最终Debug下载、校验和复位记录
- `phase09-final-clamp-validation.json`：最终上电默认、限幅和ESTOP读回
- `phase09-final-600s.json`：600秒耐久及RTOS deadline证据
- `phase09-safety-live.json`：Arm门控、timeout和ESTOP实机证据
- `phase09-mqtt-live.json`：retained/duplicate真实Broker证据
- `manual-control-results.csv`、`servo-calibration.csv`、`safety-validation.csv`：逐项结论
