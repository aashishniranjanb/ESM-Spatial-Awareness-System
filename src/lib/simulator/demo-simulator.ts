import type { SensorMessage } from "@/lib/serial/protocol";
import type { VisionOverlay } from "@/components/scan-viewer";

export class DeterministicDemoSimulator {
  private step = 0;
  private seed: number;
  private startTime = 0;

  constructor(seed: number = 42) {
    this.seed = seed;
    this.reset();
  }

  public reset() {
    this.step = 0;
    this.startTime = Date.now();
  }

  public getNextSample(): { sample: SensorMessage; detections: VisionOverlay[] } {
    this.step++;
    const ts_ms = this.startTime + this.step * 250; // 4 Hz rate like hardware

    // Simulated wearer sweeping head gently left-to-right (-35° to +35°)
    const angleRad = Math.sin(this.step * 0.08) * (35 * (Math.PI / 180));
    const gyroY = Math.cos(this.step * 0.08) * 0.08 * (35 * (Math.PI / 180));

    // Simulated room wall / corridor distance: 70cm to 260cm
    const distance_cm = 120 + Math.sin(this.step * 0.12) * 55 + (this.step % 17 === 0 ? 40 : 0);

    const sample: SensorMessage = {
      v: 1,
      type: "sample",
      ts_ms,
      distance_cm: Math.round(distance_cm * 10) / 10,
      echo_valid: true,
      accel_m_s2: { x: 0.1, y: 9.81, z: 0.2 },
      gyro_rad_s: { x: 0.0, y: gyroY, z: 0.0 },
    };

    // Cycle through detected obstacles
    const simulatedObjects = [
      { label: "Person (Ahead)", dist: 1.4, x: 0.0, z: -1.4, conf: 0.92 },
      { label: "Low Table", dist: 2.2, x: -0.4, z: -2.2, conf: 0.86 },
      { label: "Doorway Post", dist: 3.1, x: 0.5, z: -3.1, conf: 0.89 },
    ];
    const target = simulatedObjects[this.step % simulatedObjects.length];

    const detections: VisionOverlay[] = [
      {
        id: `demo-${this.step}`,
        label: target.label,
        confidence: target.conf,
        est_distance_m: target.dist,
        spatial_coords: { x: target.x, y: 0.1, z: target.z },
        is_approximate: true,
      },
    ];

    return { sample, detections };
  }
}
