# motionctl CLI参考

安装：`python -m pip install -e .\host`。所有串口命令必须显式传入`--port`，不会选择第一个COM口。

```text
python -m motionctl ports
python -m motionctl doctor --port COM4 --baud 115200
python -m motionctl ping --port COM4 --count 100
python -m motionctl info --port COM4
python -m motionctl status --port COM4
python -m motionctl config get --port COM4
python -m motionctl config set --port COM4 --telemetry-hz 10 --filter-alpha 0.2
python -m motionctl calibrate --port COM4 --wait
python -m motionctl stream start --port COM4
python -m motionctl stream stop --port COM4
python -m motionctl monitor --port COM4 --duration 30
python -m motionctl capture --port COM4 --duration 60 --output artifacts/phase06/session-001
python -m motionctl validate artifacts/phase06/session-001
python -m motionctl report artifacts/phase06/session-001 --output artifacts/phase06/session-001/report
python -m motionctl session --port COM4 --duration 60 --output artifacts/phase06/final-validation
```

退出码：0成功；1一般运行错误；2参数错误；3串口/连接错误；4协议错误；5设备命令错误；6校验失败；7报告失败。默认仅显示简洁错误，`--verbose`用于开发诊断。
