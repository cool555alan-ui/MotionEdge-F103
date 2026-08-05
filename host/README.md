# MotionEdge host tools

安装设备工具和离线图表依赖：

```powershell
python -m pip install -e .\host
python -m motionctl --help
```

`motionctl`使用固件二进制协议v1。常用流程：

```powershell
python -m motionctl ports
python -m motionctl doctor --port COM4
python -m motionctl ping --port COM4 --count 100
python -m motionctl session --port COM4 --duration 60 --output artifacts/phase06/final-validation
```

旧版`host/motionctl.py`的CSV模拟、校验、汇总、回放和文本记录入口继续保留，用于Phase 3
回归。模拟数据只用于无硬件测试，不代表真实传感器测量，也不会写入Phase 6实机报告目录。
