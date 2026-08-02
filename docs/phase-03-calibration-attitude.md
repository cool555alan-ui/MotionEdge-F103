# Phase 3：校准与姿态数据链

## 数据处理流程

```text
MPU6500原始14字节帧
→ mg/mdps整数缩放
→ 时间戳、量程、全零、固定值、饱和及总线状态检查
→ 非阻塞静止校准与偏差修正
→ 六通道一阶低通滤波
→ 加速度Roll/Pitch + 陀螺仪积分 + 互补滤波
→ MotionFrame
→ 100 ms限频CSV遥测
```

`SensorService`按10 ms周期执行一次有界读取并产生单调序号。`MotionService`只处理新序号，
重复调用不会重复消费相同样本。异常样本被丢弃，不覆盖最近的有效姿态。

## 坐标系和单位

传感器坐标系定义为X轴向前、Y轴向右、Z轴向上；Roll绕X轴，Pitch绕Y轴。MPU6500
复位默认量程按±2 g和±250 dps换算，数据链内部使用mg和mdps整数。姿态对外使用
0.01°整数，避免在固件日志中进行浮点格式化。

## 静止校准

校准状态机每次调用只处理一个样本。角速度任一轴超过5000 mdps，或加速度模长偏离
1 g超过150 mg时拒绝样本。接受500个样本后，使用64位累加器计算三轴平均值。

陀螺仪静止均值作为零偏。加速度X/Y静止均值作为基础偏差。Z轴静止读数同时包含重力，
因此Z偏差计算为平均值减去当前方向的`+1000 mg`或`-1000 mg`，不能直接把Z均值校为0；
否则姿态估计会失去重力参考。本阶段结果仅保存在RAM，不写入Flash。

## 数据质量

状态标志覆盖：

- `STALE`：时间戳未更新；
- `ALL_ZERO`：六轴全部为0；
- `ACCEL_RANGE`：加速度单轴或模长超出合理范围；
- `GYRO_RANGE`：角速度超出默认量程；
- `SATURATED`：数据贴近量程极限；
- `BUS_ERROR`：设备读取失败；
- `FIXED`：连续固定样本达到配置上限。

单次异常只丢弃当前样本；连续5次异常后运动服务进入`DEGRADED`。连续5个有效样本后
允许恢复到`RUNNING`或`CALIBRATING`，并记录恢复次数。

## 低通与姿态估计

一阶低通公式为`y = alpha*x + (1-alpha)*y`，默认`alpha=0.2`。第一个样本直接建立
滤波初值。

加速度角使用：

```text
roll  = atan2(ay, az)
pitch = atan2(-ax, sqrt(ay² + az²))
```

Pitch分母使用Y/Z平方和，避免单个分量接近0时发散。陀螺仪使用真实时间戳差积分，
`uint32_t`无符号减法支持毫秒计数器回绕。时间差为0或超过200 ms时拒绝更新。
互补滤波默认使用98%陀螺仪预测和2%加速度角。

## CSV格式

列顺序固定为：

```text
timestamp_ms,sequence,status_flags,calibrated,ax_mg,ay_mg,az_mg,gx_mdps,gy_mdps,gz_mdps,roll_cdeg,pitch_cdeg
```

CSV只包含整数，`ax_mg`至`gz_mdps`来自校准后的低通输出，行尾为CRLF。应用最多每
100 ms发送一帧，并在首帧前发送一次表头。

## Python工具

```powershell
python host\motionctl.py simulate --seconds 5 --output data\simulated.csv
python host\motionctl.py validate data\simulated.csv
python host\motionctl.py summary data\simulated.csv
python host\motionctl.py replay data\simulated.csv --speed 10
python host\motionctl.py record --port COM5 --baud 115200 --output data\capture.csv
```

`simulate`生成静止、Roll变化和Pitch变化片段，并在控制台明确标记`SIMULATED DATA`。
这些数据只验证工具、格式和算法场景，不是实际传感器测量。只有`record`依赖pyserial。

## 当前验证边界

Windows主机测试覆盖滤波、校准、姿态、时间回绕、异常降级/恢复和CSV；Python测试覆盖
解析、损坏数据、时间与序号、汇总和模拟；ARM GCC完成STM32 Debug交叉编译。

2026-08-02 实板完成 ST-LINK 烧录复位、USART1 CSV、500样本静止校准和倾斜响应验证。
本次短时采集不等于绝对角度精度、六面标定、温漂或长期漂移验证。

## 后续精度验证清单

1. 六个静止朝向检查加速度幅值和符号；
2. 已知角度治具检查Roll/Pitch方向和误差；
3. 长时间静止记录噪声、温漂和陀螺漂移；
4. 在不同供电和线长条件下复测I²C稳定性。
