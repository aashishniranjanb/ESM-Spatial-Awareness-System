# EchoMap System Architecture

## 1. Overview & Principles
EchoMap is an assistive-technology research prototype designed for real-time spatial awareness using ultrasonic range measurements and inertial motion tracking. It connects an embedded ESP32 Dev Module to a browser-based Next.js workspace and an asynchronous Python/FastAPI backend.

> [!WARNING]
> This system is an experimental research prototype and is **not a certified mobility aid**. A single ultrasonic sensor and a 6-axis IMU without a magnetometer cannot perform full SLAM or reconstruct complex real-world rooms safely. Established primary mobility aids must always remain in use.

---

## 2. Component Architecture

```
                  +-----------------------------------+
                  |      Hardware: ESP32 DevKit       |
                  |  - HC-SR04 Ultrasonic (TRIG:5/18) |
                  |  - MPU6050 6-DOF IMU (I2C:21/22)  |
                  +-----------------+-----------------+
                                    | USB CDC Serial (115200 baud)
                                    v
                  +-----------------------------------+
                  |     Frontend Next.js Client       |
                  |  - Web Serial API Adapter         |
                  |  - Three.js / R3F Spatial Canvas  |
                  |  - Camera Panel (Laptop Webcam)   |
                  |  - Deterministic Demo Simulator   |
                  |  - Harmonic Proximity & Speech    |
                  +-----------------+-----------------+
                                    | WebSocket / JSON
                                    v
                  +-----------------------------------+
                  |     FastAPI Python Backend        |
                  |  - /api/v1/sessions CRUD & Export |
                  |  - /ws/{session_id} Event Hub     |
                  |  - Spatial Transformation Pipeline|
                  |  - Vision Provider Interface      |
                  |  - SQLite (aiosqlite) Persistence |
                  +-----------------------------------+
```

---

## 3. Data Classification
To ensure scientific clarity, spatial data is strictly partitioned into three tiers:
1. **Measured:** Verified sensor points produced only from valid ultrasonic echoes ($2\text{ cm} \le d \le 400\text{ cm}$) and timestamped readings.
2. **Estimated:** Coordinates derived from gyroscope yaw integration, accelerometer gravity tilt, or computer vision approximate bounding boxes.
3. **Illustrative:** Contextual 3D environment fixtures (floor grids, wall slices, door frames) or synthetic walkthrough data generated in Demo Mode.

---

## 4. Coordinate Reference Frame
- **Origin $(0, 0, 0)$:** Centered at the wearer's position on the ground plane.
- **Axes:** Right-handed coordinate system (standard OpenGL / Three.js convention):
  - $+X$: Rightward from wearer
  - $+Y$: Upward (normal to ground)
  - $-Z$: Forward facing direction
- **Projection Formula:**
  $$\begin{aligned}
  r &= \frac{\text{median\_dist\_cm}}{100} \\
  x &= r \cdot \sin(\text{yaw}) \cdot \cos(\text{pitch}) \\
  y &= r \cdot \sin(\text{pitch}) \\
  z &= -r \cdot \cos(\text{yaw}) \cdot \cos(\text{pitch})
  \end{aligned}$$
