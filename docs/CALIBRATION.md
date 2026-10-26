# EchoMap Sensor Calibration & Transformation Guide

## Hardware Specifications
- **Board:** ESP32 Dev Module
- **Ultrasonic Sensor:** HC-SR04 (TRIG: GPIO5, ECHO: GPIO18 via voltage divider)
- **IMU:** GY-521 / MPU6050 6-DOF (SDA: GPIO21, SCL: GPIO22)
- **Telemetry Frequency:** ~4.0 Hz (250 ms period)
- **Baud Rate:** 115200 baud

## Calibration Procedures

### 1. Distance Zero & Scale Calibration
Ultrasonic pulse velocity depends on ambient temperature $T$ (°C):
$$v_{\text{sound}} \approx 331.3 + 0.606 \times T \quad (\text{m/s})$$
At standard room temperature (20°C), $v_{\text{sound}} \approx 343.4\text{ m/s} = 0.03434\text{ cm/\mu s}$.

### 2. Relative Pose Zeroing
1. Hold the wearer's glasses steady, horizontal, and oriented in the intended forward direction.
2. Click **Zero Relative Pose** in the UI.
3. This sets initial $\text{yaw} = 0$, $\text{pitch} = 0$, and clears accumulated drift.

### 3. Gyroscope Drift Limitation
The MPU6050 does not feature a 3-axis magnetometer. Consequently:
- Gyroscope yaw integration is subject to slow continuous drift (~0.5° to 2° per minute).
- Yaw is valid strictly as a **relative directional estimate during active scanning sweeps**, not an absolute navigational heading.
