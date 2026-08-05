# Phase 7 validation method

Automated tests cover the topic contract, JSON/UUID/expiry validation, QoS/retain/LWT, fixed queues, bounded deduplication, retry accounting, strict configuration, and Flow integrity. Integration validation uses the isolated real Mosquitto instance and a clearly marked simulated serial device to test command correlation, duplicate/expired/retained rejection, LWT, broker outage, and re-subscription.

Final acceptance is separate and must use the real STM32F103C8T6/MPU6500 on 115200 8N1 for at least 600 seconds. It records raw MQTT, compact metrics, 100 command results, broker recovery, LWT, sequence integrity, latency, queue high-water marks, and process memory. The operator keeps the board still for the first 30 seconds, moves it through four tilts, confirms calibration while stationary, and visually checks the local Node-RED page.

`gateway_to_nodered` is a same-host local-broker observation. It is not a cross-host or public-internet latency claim. A result is never promoted from simulated integration to real-hardware PASS.
