# MotionEdge host tools

`motionctl.py`使用与固件一致的12列整数CSV格式。除串口采集命令外只依赖Python标准库；
`record`命令需要安装`requirements.txt`中的`pyserial`。

```powershell
python host\motionctl.py simulate --seconds 5 --output data\simulated.csv
python host\motionctl.py validate data\simulated.csv
python host\motionctl.py summary data\simulated.csv
python host\motionctl.py replay data\simulated.csv --speed 10
python host\motionctl.py record --port COM5 --baud 115200 --output data\capture.csv
```

`simulate`输出仅为测试姿态变化和工具链的模拟数据，不代表真实传感器测量。
