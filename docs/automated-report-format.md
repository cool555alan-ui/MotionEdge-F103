# 自动报告格式

会话目录包含`session-metadata.json`、`serial-raw.bin`、`telemetry.csv`、`commands.csv`和`capture-summary.json`。原始文件与遥测CSV用于本地证据，不提交Git。

`report/`包含：

- `report.md`：会话、配置、完整性、姿态、健康、命令性能、验收矩阵和结论；
- `report.json`：完整结构化元数据、指标、规则实际值和原因；
- `metrics.csv`：展平的指标表；
- `attitude.png`：Roll/Pitch随会话时间变化；
- `telemetry-timing.png`：遥测间隔随会话时间变化。

所有时间延迟和RTT使用主机单调时钟。设备时间与主机接收单调时间同时保存在遥测CSV。缺失字段使用`NOT_TESTED`或`NOT_AVAILABLE`，不会自动通过。
