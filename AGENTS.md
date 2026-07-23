# MotionEdge-F103 Agent Rules

- 本项目目标 MCU 为 STM32F103C8T6，主开发环境仅使用 Visual Studio Code。
- 外设配置和初始化代码必须由 STM32CubeMX 生成；STM32CubeMX 必须生成 CMake 工程，并使用 GCC 工具链。
- 不使用 Keil、PlatformIO 或传统 STM32CubeIDE 桌面版。
- 不迁移、复制或修改任何旧项目代码。
- 禁止手工生成 startup 文件和 linker script。
- 禁止修改 STM32CubeMX 自动生成区域；只允许修改 `USER CODE` 区域或独立用户模块。
- HAL 调用只能出现在 BSP 或驱动适配层；算法模块不得依赖 STM32 HAL。
- 固件禁止使用 `malloc`、`calloc` 和 `realloc`。
- 新代码必须检查空指针、长度和返回状态。
- 每次修改后必须运行构建。
- 不允许通过删除代码或关闭警告来掩盖编译错误。
