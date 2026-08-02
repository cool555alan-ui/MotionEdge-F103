# MotionEdge 首次真实硬件验收报告

- 验证日期：2026-08-02T22:24:55+08:00
- 固件提交：`3dd5d5da3cfe56bd3c9e8574446a3cc463b32163`
- 固件版本：`0.4.1`
- 源码状态：working tree with uncommitted changes
- 构建配置：`Debug`
- ST-LINK：SN=37FF71064E573436F8051F43_FW=V2J37S7_Voltage=3.33V_DeviceID=0x410
- 串口：`COM4`，`115200 8N1`，无流控
- MPU6500 地址：0x68
- WHO_AM_I：0x70

## 数据统计

- 总帧数：1450（阶段A 619，阶段B 831）
- 估算丢帧：0；sequence 回退/重复：0；复位边界：0
- 平均采样间隔：100.0 ms；中位数：100 ms
- 静止加速度模长：mean=1000.4660344132395 mg，stddev=1.3011471211567955 mg，range=994.0065392139028..1007.0024826185881 mg
- 应用状态计数：{'RUNNING': 169}
- Roll：-24.87..20.25 deg
- Pitch：-31.98..31.88 deg
- 加速度各轴：ax_mg=-611..536 mg, ay_mg=-391..424 mg, az_mg=729..1188 mg
- 角速度各轴：gx_mdps=-133640..107073 mdps, gy_mdps=-159928..187766 mdps, gz_mdps=-34183..25113 mdps
- 方向确认：工具不自动判定正负方向；请用户根据实际动作确认。

## 分级结果

- `st_link_connection`：**PASS**
- `firmware_flash`：**PASS**
- `program_reset_start`：**PASS**
- `serial_open`：**PASS**
- `startup_log`：**PASS**
- `i2c_address`：**PASS**
- `who_am_i`：**PASS**
- `sensor_ready`：**PASS**
- `calibration_started`：**PASS**
- `calibration_complete`：**PASS**
- `valid_attitude_frames`：**PASS**
- `timestamp_continuity`：**PASS**
- `sequence_continuity`：**PASS**
- `static_acceleration_magnitude`：**PASS**
- `motion_data_change`：**PASS**
- `roll_pitch_change`：**PASS**
- `output_bounds`：**PASS**
- `post_motion_stability`：**PASS**
- `application_state`：**PASS**
- `serial_parse_errors`：**PASS**

## 当前通过项

st_link_connection, firmware_flash, program_reset_start, serial_open, startup_log, i2c_address, who_am_i, sensor_ready, calibration_started, calibration_complete, valid_attitude_frames, timestamp_continuity, sequence_continuity, static_acceleration_magnitude, motion_data_change, roll_pitch_change, output_bounds, post_motion_stability, application_state, serial_parse_errors

## 警告项

无

## 失败项

无

## 尚未验证项

无
