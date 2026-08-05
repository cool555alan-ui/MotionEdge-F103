# RTOS任务设计

## 调度边界

FreeRTOS只负责周期调度、同步、事件状态和命令传递。MPU6050/MPU6500兼容驱动、
I²C抽象、校准、滤波、姿态估计、CRC、协议编解码及配置校验仍是RTOS无关模块。
`App_RunOnce()`保留为裸机主机测试兼容入口，但STM32的`main`只启动RTOS调度器，
不会同时运行两套调度路径。

## 任务配置

| 任务 | 周期 | 优先级 | 初始静态栈 |
|---|---:|---|---:|
| SensorTask | 10 ms | AboveNormal | 1024 Bytes |
| CommunicationTask | 2 ms轮询 | AboveNormal | 1024 Bytes |
| TelemetryTask | 100 ms | Normal | 1024 Bytes |
| HealthTask | 1000 ms | Low | 512 Bytes |

SensorTask使用`osDelayUntil()`绝对周期唤醒。当前没有独立微秒计时器，因此执行时间和
抖动以1 ms RTOS tick测量，再换算成微秒字段；小于1 ms的差异不可分辨，报告不得把它
解释成真实微秒精度。所有任务在实板运行后记录字节单位的stack high-water mark，随后
才能决定是否缩减栈。

## 所有权和同步

SensorTask是MotionFrame唯一发布者。它把最新完整帧复制到互斥锁保护的静态快照；
TelemetryTask只取最新序号，不把100 Hz全部样本排入10 Hz队列，因此不会形成必然积压。
临界区内只复制结构，不执行算法、日志或UART操作。

CommunicationTask每2 ms执行一次有界RX和Parser。解析完成后只把命令头和最多10 B的
命令参数复制到容量8的静态紧凑队列，由SensorTask消费并还原为原CommandService接口。
超长请求保留原始长度，仍由原服务拒绝，不会因压缩而被错误接受。这样修改校准、配置
或传感器状态的命令不会跨任务直接写入其状态；队列存储区由1088 B降为144 B，且不使用
运行期通用堆。

文本日志、CSV、命令响应和二进制遥测共用一个有限等待UART互斥锁。选择互斥锁而不是
额外TX任务，是为了避免在20 KiB RAM器件上增加任务栈和大型TX队列；协议模式仍禁止
文本与二进制混流。互斥锁等待超时、命令队列满和快照锁超时均累计统计。

事件标志只表达SYSTEM_READY、SENSOR_ONLINE、CALIBRATED、TELEMETRY_ENABLED、
PROTOCOL_MODE、DEGRADED和FAULT，不携带运动数据。

## 静态内存和时间基准

四个应用任务的栈和TCB、两个互斥锁、命令队列控制块与存储区、事件标志控制块全部由
静态数组提供。CubeMX生成的`defaultTask`仍由生成代码动态建立，但进入后立即调用
`osThreadExit()`，其TCB和栈不会永久占用。`TOTAL_HEAP_SIZE`保持3072 B，用于CubeMX/
CMSIS适配层保留路径；HealthTask输出当前和历史最小剩余堆。

FreeRTOS使用1 kHz SysTick。HAL毫秒时间基准由TIM4提供，I²C/UART有限超时继续使用HAL
tick。任务周期采用RTOS tick，运动样本时间戳继续使用毫秒语义，两者不混用单位。

## 健康判定

每个任务记录运行次数、deadline miss、最大执行时间、最大抖动、最近心跳和最小剩余栈。
`RtosMonitor_GetSnapshot()`提供一致的统计副本，`RtosMonitor_AllCriticalTasksAlive()`为
后续看门狗提供判定入口。本阶段不启用独立看门狗。
