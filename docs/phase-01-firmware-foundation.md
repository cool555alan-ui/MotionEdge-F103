# Phase 1：固件基础框架

## 阶段目标

本阶段在 STM32CubeMX 生成的 STM32F103C8T6 CMake 工程上建立可维护的软件分层、
非阻塞主循环、可移植逻辑模块和主机测试入口。目标是先验证软件结构和交叉编译链，
不把未连接硬件的行为描述为已验证。

## 软件分层与依赖方向

```text
Src/main.c
    └── App
        ├── Services
        ├── Middleware
        ├── Common
        └── BSP
            └── CubeMX HAL / generated handles
```

- `App/` 负责系统编排、版本、配置和应用状态。
- `BSP/` 封装 PC13 LED 极性、USART1 句柄和 HAL 状态码。
- `Common/` 提供不依赖 HAL 的软件定时器。
- `Middleware/` 提供通过写函数注入输出端的 Logger。
- `Services/` 维护运行时间、循环、心跳和日志失败统计，不直接输出日志。
- `Tests/Host/` 仅构建纯逻辑模块，不使用 ARM 工具链或 STM32 HAL。

HAL 调用只存在于 BSP 和 CubeMX 生成代码中。Logger、软件定时器、应用状态和健康
统计可以由 Windows 本机 C 编译器构建。

## 模块职责

### LED BSP

`BspLed_*` 使用 CubeMX 生成的 `STATUS_LED_Pin` 和 `STATUS_LED_GPIO_Port`。PC13
按低电平点亮封装在 BSP 内部，应用层只表达开、关和切换。GPIO 初始化仍完全由
`MX_GPIO_Init()` 执行。

### UART BSP

`BspUart_Write()` 使用 CubeMX 的 `huart1` 和 `HAL_UART_Transmit()`，发送超时固定为
`APP_UART_TIMEOUT_MS`。模块检查空指针、长度和 HAL 返回状态，不重定向 `printf`，
也不拼接业务日志。

### Logger

Logger 使用 `LogWriteFunction_t` 注入输出端，因此不包含 HAL 或 USART 头文件。固定
静态缓冲区避免动态内存；`snprintf`/`vsnprintf` 的返回值用于拒绝截断日志。函数注入
让同一实现既可连接 UART BSP，也可在主机测试中连接内存捕获函数。

### 软件定时器

到期判断使用 `now_ms - last_run_ms` 的无符号减法，因此 32 位毫秒计数器回绕时仍能
计算经过时间。到期后基准按完整周期推进，而不是直接赋值为当前时间，从而减少主循环
抖动造成的长期漂移。

### 应用状态和健康服务

应用状态覆盖启动、初始化、运行、降级和故障。健康服务记录启动时间、最新时间、主循环
次数、心跳次数和日志失败次数；快照中的运行时间同样使用无符号减法支持回绕。

## 主循环流程

1. CubeMX 完成 HAL、时钟、GPIO、I²C1 和 USART1 初始化。
2. `App_Init(HAL_GetTick())` 初始化 BSP、Logger、软件定时器、状态和健康服务。
3. 主循环每次调用 `App_RunOnce(HAL_GetTick())`，不使用阻塞延时。
4. 每 500 ms 切换一次 LED 并记录心跳。
5. 每 1000 ms 读取健康快照，通过 Logger 输出整数统计。

UART 发送目前是唯一允许的短时阻塞操作，超时为 20 ms。

## 验证方式

软件验证按以下顺序执行：

1. `tools/test-host.ps1`：用 Windows 本机 C 编译器运行定时器、状态和 Logger 测试。
2. `tools/build.ps1`：使用 ST Bundle 的 GCC、CMake 和 Ninja 交叉编译 Debug 固件。
3. `tools/check-phase1.ps1`：检查分层、禁止 API、CubeMX 保护边界、产物和 Git 状态。
4. `git diff --check`：检查补丁格式和行尾空白。

## 已完成的软件验证

- 软件定时器的空指针、零周期、到期、连续周期、漂移和回绕逻辑可在主机运行。
- 应用状态的初始化、设置、读取、字符串和非法值处理可在主机运行。
- Logger 的初始化、过滤、格式、截断、空参数和 CRLF 结尾可在主机运行。
- STM32 Debug 固件可由 ARM GCC 链接，并可检查 ELF、MAP、Flash 和 RAM 占用。

## 待硬件验证

- PC13 LED 是否与具体开发板电路一致并按预期闪烁。
- USART1 的波特率、电平、接线和实际日志输出。
- ST-LINK 烧录、复位和断点调试。

在完成上述实机步骤前，不声称 LED、串口或烧录已经通过硬件验证。
