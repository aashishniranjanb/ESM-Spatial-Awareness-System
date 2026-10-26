# ESM Scene Coordinates & Transformation Specification

This document details the spatial reference frame, sensor mounting geometry, transformation hierarchy, and data provenance tiers used across the **ESM — Spatial Awareness System**.

---

## 1. Local Coordinate Reference Frame

The 3D spatial viewer follows the standard **Right-Handed OpenGL / Three.js** convention:

| Axis | Spatial Orientation | Wearer Perspective | Color in AxesHelper |
|---|---|---|---|
| **+X** | Horizontal Right | Wearer's Right side | Red |
| **+Y** | Vertical Up | Normal to floor / Upward | Green |
| **+Z** | Backward | Behind the wearer | Blue |
| **-Z** | Forward | Direct acoustic sensing direction ahead | (Negative Blue) |

- **Origin $(0, 0, 0)$:** Situated on the floor plane directly between the wearer's feet.
- **Wearer Eye / Sensor Level:** $(0, 1.57, -0.16)\text{ m}$ (standard standing head height).
- **Floor Plane:** $Y = 0\text{ m}$ (grid helper rendered at $Y = 0$).

---

## 2. Sensor Placement & Forward Projection

The wearable device is worn at eye level:
- **HC-SR04 Ultrasonic Transducer:** Fixed facing directly along the forward vector:
  $$\hat{\mathbf{v}}_{\text{sensor}} = \begin{bmatrix} 0 \\ 0 \\ -1 \end{bmatrix}$$
- **GY-521 (MPU6050) Orientation:**
  - $Y$-gyroscope measures azimuthal angular velocity $\omega_y$ (yaw).
  - Accelerometer $(a_x, a_y, a_z)$ measures the gravity reference vector for tilt (pitch $\theta$ and roll $\phi$).

### Transformation Equations:
When a valid range sample $d$ (in cm) is accepted:
1. Distance in metres:
   $$r = \frac{d}{100.0}$$
2. Azimuth (relative yaw $\psi$) and pitch ($\theta$):
   $$\begin{aligned}
   x &= r \cdot \sin(\psi) \cdot \cos(\theta) \\
   y &= 1.57 + r \cdot \sin(\theta) \\
   z &= -r \cdot \cos(\psi) \cdot \cos(\theta)
   \end{aligned}$$

---

## 3. Data Provenance Tiers

To avoid scientific ambiguity or false safety expectations, every element rendered in ESM carries one of three explicit provenance labels:

1. **MEASURED (Cyan / Amber / Red Points):**
   - Direct physical observations produced by the HC-SR04 ultrasonic sensor.
   - Requires `echo_valid == true` and range in $[2, 400]\text{ cm}$.
   - Filtered against isolated multipath spikes by a 5-sample rolling median window.

2. **ESTIMATED (Purple Bounding Indicators):**
   - Spatial coordinates calculated from mathematical derivations:
     - Gyroscopic yaw integration (relative, drift-prone).
     - Accelerometer gravity-tilt estimates.
     - Monocular optical estimates from the laptop webcam.

3. **ILLUSTRATIVE (Dark Navy / Grey Mesh Geometry):**
   - 3D models placed for situational context (walls, chairs, doors, curbs, pedestrians).
   - **Crucial Rule:** An illustrative asset in the scene does NOT imply a physical obstacle has been detected by the sensors.

---

## 4. Hardware Limitations & Drift

> [!WARNING]
> - **MPU6050 Drift:** The sensor lacks a 3-axis magnetometer. Relative yaw drifts over time ($\approx 0.5^\circ - 2^\circ / \text{min}$). The **Zero Relative Pose** control in the ESM interface resets this accumulation.
> - **Acoustic Beam Angle:** The HC-SR04 has an acoustic cone of approximately $15^\circ$. It reports the closest reflecting surface within that cone, not an infinitesimal ray.
