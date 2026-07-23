# STM32 开发环境配置状态

检测日期：2026-07-23

| 项目 | 状态 | 检测结果 | 下一步 |
| -- | -- | ---- | --- |
| VS Code | 已完成 | VS Code 1.129.1，`code` 可用 | 重载窗口以激活新扩展 |
| ST官方扩展包 | 已完成 | `stmicroelectronics.stm32-vscode-extension` 3.10.0 及官方依赖已安装 | 重载 VS Code 后复检 |
| Cube CLI | 已完成 | 扩展内 `cube.exe` 0.10.3 已验证；当前普通终端 PATH 未激活 | 在 VS Code 重载后运行诊断脚本 |
| STM32工具Bundle | 已完成 | 已验证 CMake、Ninja、GNU tools、Programmer、GDB Server 等官方 Bundle | 无 |
| STM32F1设备包 | 已完成 | `STMicroelectronics.stm32f1xx_dfp` 1.2.0 已展开安装 | 无 |
| STM32CubeMX | 待用户授权 | 未在卸载信息、开始菜单和常见路径中找到；winget 不可用 | 从 ST 官网安装，并接受许可协议/按需登录 |
| Git | 已完成 | Git 2.55.0.windows.2 | 无 |
| Arm GCC | 已完成 | Arm GNU Toolchain 14.2.1 已验证 | 无 |
| CMake | 已完成 | Bundle CMake 4.3.1 已验证 | 由 Cube/VS Code 环境调用 |
| Ninja | 已完成 | Bundle Ninja 1.13.2 已验证 | 由 Cube/VS Code 环境调用 |
| STM32CubeProgrammer CLI | 已完成 | Bundle STM32CubeProgrammer 2.23.0 已验证 | 生成并构建固件后再验证实机烧录 |
| ST-LINK驱动 | 已完成 | Windows 卸载信息存在 STLinkWinUSB 2.02；GDB Server 7.14.0 已验证 | 连接硬件后验证实机调试 |
| 项目目录 | 已完成 | `C:\STM32\MotionEdge-F103` 已初始化，不含伪造固件文件 | 用 CubeMX 在该目录生成工程 |
| Git仓库 | 已完成 | Git 仓库已初始化；全局用户名与邮箱已配置 | 已创建首次提交 |
| CubeMX工程 | 待CubeMX生成工程 | 尚无 `.ioc/.ioc2`、`CMakeLists.txt` 或 `CMakePresets.json` | 用 CubeMX 生成最小 CMake + GCC 工程 |
| 首次STM32构建 | 待CubeMX生成工程 | 当前没有可构建固件 | 生成工程后运行 `tools\build.ps1` |

## 需要用户完成

1. 重载或重启 VS Code。
2. 从 STMicroelectronics 官方网站安装 STM32CubeMX；安装过程可能要求接受 ST 许可协议或登录。
3. 安装后按 README 和最终摘要创建最小工程。
4. 重新运行 `powershell -ExecutionPolicy Bypass -File .\tools\diagnose-stm32-env.ps1`。
5. 再运行 `powershell -ExecutionPolicy Bypass -File .\tools\build.ps1`。
