import math
from typing import Optional, List, Tuple
from app.schemas.schemas import SensorSampleBase, SpatialPointBase, Vec3

class SpatialPipeline:
    """
    Server-side and offline spatial transformation pipeline.
    Replicates & complements frontend relative mapping with configurable calibration:
      - cm to metres conversion
      - distance offset and scale calibration
      - rolling median filter to suppress isolated ultrasonic multipath spikes
      - accelerometer tilt estimation
      - gyroscope integration with bias correction
      - relative XYZ coordinate projection
    """

    def __init__(
        self,
        distance_offset_cm: float = 0.0,
        distance_scale: float = 1.0,
        min_distance_cm: float = 2.0,
        max_distance_cm: float = 400.0,
        window_size: int = 5,
        gyro_bias: Optional[Vec3] = None
    ):
        self.distance_offset_cm = distance_offset_cm
        self.distance_scale = distance_scale
        self.min_distance_cm = min_distance_cm
        self.max_distance_cm = max_distance_cm
        self.window_size = window_size
        self.gyro_bias = gyro_bias or Vec3(x=0.0, y=0.0, z=0.0)

        # State
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.last_ts: Optional[int] = None
        self.distance_window: List[float] = []
        self.accepted_count = 0
        self.rejected_count = 0

    def reset(self):
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.last_ts = None
        self.distance_window.clear()
        self.accepted_count = 0
        self.rejected_count = 0

    def project_sample(self, sample: SensorSampleBase) -> Tuple[Optional[SpatialPointBase], Optional[str]]:
        """
        Projects a raw sensor sample into a 3D spatial point in the wearer's local frame.
        Coordinate conventions:
          X: Right (+X)
          Y: Up (+Y)
          Z: Forward is Negative Z (-Z), standard OpenGL / Three.js convention.
        """
        # 1. Orientation Update from Gyroscope
        if self.last_ts is not None and sample.gyro_rad_s is not None:
            dt = max(0.0, min(0.25, (sample.ts_ms - self.last_ts) / 1000.0))
            # Gyro Y is assumed vertical / yaw rotation
            corrected_gyro_y = sample.gyro_rad_s.y - self.gyro_bias.y
            self.yaw += corrected_gyro_y * dt
            # Normalize yaw into [-pi, pi]
            self.yaw = math.atan2(math.sin(self.yaw), math.cos(self.yaw))

        # 2. Tilt Update from Accelerometer
        if sample.accel_m_s2 is not None:
            ax, ay, az = sample.accel_m_s2.x, sample.accel_m_s2.y, sample.accel_m_s2.z
            norm = math.sqrt(ax * ax + ay * ay + az * az)
            # Only use when near 1g gravity norm (8 to 12 m/s^2)
            if 8.0 <= norm <= 12.0:
                self.pitch = math.atan2(-ax, math.sqrt(ay * ay + az * az))
                self.roll = math.atan2(ay, az)

        self.last_ts = sample.ts_ms

        # 3. Echo Validity Check
        if not sample.echo_valid or sample.distance_cm is None:
            self.rejected_count += 1
            return None, "No valid ultrasonic echo detected"

        # Apply calibration: calibrated = (raw + offset) * scale
        calibrated_cm = (sample.distance_cm + self.distance_offset_cm) * self.distance_scale

        if calibrated_cm < self.min_distance_cm or calibrated_cm > self.max_distance_cm:
            self.rejected_count += 1
            return None, f"Distance {calibrated_cm:.1f}cm outside valid range ({self.min_distance_cm}-{self.max_distance_cm}cm)"

        # 4. Spike Filtering
        self.distance_window.append(calibrated_cm)
        if len(self.distance_window) > self.window_size:
            self.distance_window.pop(0)

        sorted_window = sorted(self.distance_window)
        median_dist_cm = sorted_window[len(sorted_window) // 2]

        if len(self.distance_window) >= 3:
            baseline = sorted(self.distance_window[:-1])[len(self.distance_window[:-1]) // 2]
            if abs(calibrated_cm - baseline) > max(100.0, baseline * 1.25):
                self.rejected_count += 1
                return None, "Ultrasonic spike rejected by rolling filter"

        # 5. Coordinate Projection
        # Distance r in metres
        r = median_dist_cm / 100.0
        cp = math.cos(self.pitch)
        
        # Three.js coordinate system (Right Handed: +X right, +Y up, -Z forward)
        x = r * math.sin(self.yaw) * cp
        y = r * math.sin(self.pitch)
        z = -r * math.cos(self.yaw) * cp

        # Intensity decays with distance
        intensity = max(0.12, min(1.0, 1.0 - (r / 4.0)))
        
        # Uncertainty estimate: base sensor noise + range degradation + angular drift
        uncertainty = 0.03 + (0.02 * r) + (0.01 * abs(self.yaw))

        point = SpatialPointBase(
            id=f"{sample.ts_ms}-{self.accepted_count}",
            ts_ms=sample.ts_ms,
            x=round(x, 4),
            y=round(y, 4),
            z=round(z, 4),
            distance=round(r, 4),
            intensity=round(intensity, 3),
            uncertainty=round(uncertainty, 4),
            quality_flag="measured"
        )
        self.accepted_count += 1
        return point, None
