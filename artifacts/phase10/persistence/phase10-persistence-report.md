# Phase 10 配置持久化真实硬件验收

- 日期：2026-08-09（Asia/Shanghai）
- 固件：1.0.0，基于提交 `c00e184` 加 Phase 10 待提交变更
- MCU：STM32F103C8T6，64 KiB Flash，1 KiB/page
- Slot A：`0x0800F800`–`0x0800FBFF`
- Slot B：`0x0800FC00`–`0x0800FFFF`
- Record：54 bytes；Schema 1；CRC16-CCITT-FALSE；commit marker 最后写入

## 真实掉电结果

真实断电均由用户断开 STM32 供电至少 2 秒并重新连接。验证了：空槽回落默认值；SLOT_A generation 1 恢复 1.5° deadband；未保存的 RAM-only 2.0° 在掉电后被丢弃；SLOT_B generation 2 恢复 2.0°；Factory Reset 后再次掉电仍回落 1.0° 默认值。全部 PASS。

## 安全启动

每次重启均确认 actuator DISABLED、armed=false、owner=NONE、PID disabled、PWM=1500 us。危险运行状态未持久化。安全窗口保持 1450–1550 us，PID 输出硬限制保持 ±10 us。

## 最终候选复核

最终 Release HEX 经 ST-LINK 下载、校验并复位成功，设备报告 1.0.0。真实 CONFIG_SAVE 写入 SLOT_A generation 1，`last_save_duration_ms=2`；随后真实 Factory Reset 回到 DEFAULTS、generation 0，耗时 2 ms。

## 故障注入边界

FakeFlash 主机测试覆盖 erase/program/verify 失败、partial header/payload/CRC、无或损坏 commit、CRC 损坏、旧槽恢复和双槽无效回退。该部分是可重复软件故障注入，不冒充物理掉电注入。
