# Phase 5：FreeRTOS调度迁移

## 为什么此时加入RTOS

Phase 1～4先在裸机协作式循环中验证了板级I²C、USART、MPU6500、校准、姿态算法、CSV
和二进制协议。此后才替换调度与通信层，可以把新的并发问题与已验证的驱动和算法问题
分开定位。硬件基线固定为`v0.4-hardware-validated`。

## 迁移内容

CubeMX 6.17.0生成FreeRTOS 10.3.1与CMSIS-RTOS2框架，SysTick用于1 kHz内核节拍，
TIM4用于HAL tick。用户代码在`App/RTOS/`创建Sensor、Communication、Telemetry和
Health四个静态任务，并提供最新帧快照、容量8命令队列、UART互斥锁、事件标志及运行
监控。算法、驱动、协议和服务没有引入RTOS头文件。

实际器件WHO_AM_I为`0x70`，识别为MPU6500。兼容驱动同时接受MPU6050的`0x68`，保存
检测型号但不改动已经实板验证的寄存器数据链，也不批量重命名现有文件。

详细任务周期、栈、数据所有权和同步边界见[RTOS任务设计](rtos-task-design.md)。

## 资源基线和门限

空RTOS Debug基线为Flash 51,448 B、RAM 10,456 B。Phase 5目标为Debug Flash不超过
约62 KiB、RAM不超过约16 KiB，同时RAM不得超过20 KiB物理容量的80%。Release仅用于
优化效果对比，不能掩盖Debug越界。四个应用任务静态栈合计3584 B，RTOS堆保持3072 B，
软件定时器保持启用且应用不创建额外`osTimer`。

## 验证状态

2026-08-03软件侧结果为Phase 1～5通过、C断言466/466、Python 13/13、Debug和Release
均为0 warning。Debug保留`-g3`并采用面向调试的`-Og`，为Flash 43,288 B（66.05%）、
RAM 15,216 B（74.30%）；Release为Flash 38,148 B、RAM 15,216 B。空RTOS历史基线使用
`-O0`，因此当前Flash与51,448 B基线的数值差不能解释为纯代码增量。四个应用任务栈
合计3584 B，紧凑命令队列存储区144 B，RTOS堆仍为3072 B。

本轮用户确认暂时没有实物，Windows也没有枚举到ST-LINK或COM口，因此烧录、串口、
任务频率、实际栈余量、命令、掉线恢复和10分钟运行均为NOT_TESTED。不得声明RTOS硬件
验收通过，也不得创建`v0.5-freertos-validated`标签。当前证据见
`artifacts/rtos-validation/rtos-validation-report.md`。
