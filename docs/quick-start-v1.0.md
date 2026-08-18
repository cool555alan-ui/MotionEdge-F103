# MotionEdge-F103 v1.0 quick start

1. Connect MPU6500 I²C to PB6/PB7 and USART1 USB-TTL to PA9/PA10, with common GND.
2. Power SG90 from an independent regulated 5 V supply, connect grounds, and connect signal to PA6.
3. Flash `motionedge-f103-v1.0.0.hex` using ST-LINK/SWD.
4. Install the motionctl wheel and run `python -m motionctl doctor --port COMx`.
5. Start the local Mosquitto broker, then `motionctl gateway run --config motionedge-gateway.example.toml`.
6. Import the supplied Node-RED flow and open the local dashboard.
7. Confirm the servo path is unobstructed and ESTOP is accessible before Arm.
8. Enable Pitch attitude control only after calibration and status checks pass.

The broker prototype is local and has no TLS. The single MPU6500 measures hand-held input; SG90 motion is not fed back to that sensor, so this is not an external mechanical attitude closed loop.
