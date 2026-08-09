# Coordinate convention

Firmware defines a right-handed body frame: X points toward the front edge of the mounted breadboard, Y points toward its right edge, and Z points upward through the component side.

```text
             +X (front)
                ^
                |
    +Z (up)  o---+---> +Y (right)

Roll:  rotation about +X; atan2(+ay,+az)
Pitch: rotation about +Y; atan2(-ax,sqrt(ay²+az²))
```

With the component side upward at rest, calibrated Z acceleration is approximately +1 g. The mathematical signs above come directly from the single firmware algorithm boundary; Python, CSV, MQTT, and Node-RED do not invert them independently.

Phase 8 real-hardware confirmation completed with the component side upward and X pointing forward: raising the right edge increased Roll (positive), while raising the front edge decreased Pitch (negative). The observed changes were approximately +35.95 degrees Roll and -63.25 degrees Pitch relative to the horizontal baseline. Fixture skew can appear as cross-axis coupling and must not automatically be attributed to the estimator.
