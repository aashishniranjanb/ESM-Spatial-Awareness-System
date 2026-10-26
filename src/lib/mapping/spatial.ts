import type { SensorMessage } from "@/lib/serial/protocol";
import type { ScanPoint } from "@/components/scan-viewer";

export type Orientation = { yaw: number; pitch: number; roll: number };
export type MapperState = { orientation: Orientation; lastTs: number | null; distanceWindow: number[]; accepted: number; rejected: number };
export const initialMapperState = (): MapperState => ({ orientation: { yaw: 0, pitch: 0, roll: 0 }, lastTs: null, distanceWindow: [], accepted: 0, rejected: 0 });

const clamp = (n: number, min: number, max: number) => Math.min(max, Math.max(min, n));
function median(values: number[]) { const s = [...values].sort((a,b) => a-b); return s[Math.floor(s.length / 2)]; }

/**
 * Relative directional mapping, not SLAM. Assumes the MPU6050's Y gyro axis
 * is the device's vertical/yaw axis. Verify physical board orientation first.
 * Distances are converted from cm to metres; forward is negative Z.
 */
export function projectSample(sample: SensorMessage, state: MapperState): { point: ScanPoint | null; state: MapperState; orientation: Orientation; reason?: string } {
  const next: MapperState = { ...state, orientation: { ...state.orientation }, distanceWindow: [...state.distanceWindow] };
  const gyro = sample.gyro_rad_s;
  const accel = sample.accel_m_s2;
  if (next.lastTs !== null && gyro) {
    const dt = clamp((sample.ts_ms - next.lastTs) / 1000, 0, 0.25);
    // Y-axis integration is only a short-term relative yaw estimate; it drifts.
    next.orientation.yaw += gyro.y * dt;
    next.orientation.yaw = Math.atan2(Math.sin(next.orientation.yaw), Math.cos(next.orientation.yaw));
  }
  if (accel) {
    const { x, y, z } = accel;
    const norm = Math.sqrt(x*x + y*y + z*z);
    if (norm > 5 && norm < 15) {
      next.orientation.pitch = Math.atan2(-x, Math.sqrt(y*y + z*z));
      next.orientation.roll = Math.atan2(y, z);
    }
  }
  next.lastTs = sample.ts_ms;
  if (!sample.echo_valid || sample.distance_cm === null || !Number.isFinite(sample.distance_cm)) {
    next.rejected += 1;
    return { point: null, state: next, orientation: next.orientation, reason: "No valid echo" };
  }
  if (sample.distance_cm < 2 || sample.distance_cm > 400) {
    next.rejected += 1;
    return { point: null, state: next, orientation: next.orientation, reason: "Outside configured usable range (2–400 cm)" };
  }
  // Rolling median rejects isolated ultrasonic spikes. Reject large jumps rather than drawing false walls.
  const recent = [...next.distanceWindow, sample.distance_cm].slice(-5);
  const filtered = median(recent);
  if (next.distanceWindow.length >= 3) {
    const baseline = median(next.distanceWindow);
    if (Math.abs(sample.distance_cm - baseline) > Math.max(100, baseline * 1.25)) {
      next.rejected += 1;
      next.distanceWindow = recent.slice(-4);
      return { point: null, state: next, orientation: next.orientation, reason: "Distance spike rejected" };
    }
  }
  next.distanceWindow = recent;
  const r = filtered / 100;
  const { yaw, pitch } = next.orientation;
  const cp = Math.cos(pitch);
  const point: ScanPoint = {
    id: `${sample.ts_ms}-${next.accepted}`,
    x: r * Math.sin(yaw) * cp,
    y: r * Math.sin(pitch),
    z: -r * Math.cos(yaw) * cp,
    distance: r,
    intensity: clamp(1 - r / 4, 0.12, 1),
  };
  next.accepted += 1;
  return { point, state: next, orientation: next.orientation };
}

export function validateScanPoints(value: unknown): value is ScanPoint[] {
  if (!Array.isArray(value) || value.length > 100_000) return false;
  return value.every((p) => p && typeof p === "object" && typeof p.id === "string" && ["x","y","z","distance","intensity"].every((k) => typeof (p as Record<string, unknown>)[k] === "number" && Number.isFinite((p as Record<string, number>)[k])));
}
