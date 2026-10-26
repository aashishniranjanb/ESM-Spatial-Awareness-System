export type Vec3 = { x: number; y: number; z: number };

export type SensorMessage = {
  v: 1;
  type: "sample";
  ts_ms: number;
  distance_cm: number | null;
  echo_valid: boolean;
  accel_m_s2?: Vec3;
  gyro_rad_s?: Vec3;
};

export type SerialStatus = "unsupported" | "disconnected" | "connecting" | "connected" | "error";

export function parseSensorLine(line: string): SensorMessage {
  const value: unknown = JSON.parse(line);
  if (!value || typeof value !== "object") throw new Error("Record is not an object");
  const d = value as Record<string, unknown>;
  if (d.v !== 1 || d.type !== "sample") throw new Error("Unsupported protocol version or message type");
  if (typeof d.ts_ms !== "number" || typeof d.echo_valid !== "boolean") throw new Error("Missing timestamp or echo_valid");
  if (d.distance_cm !== null && typeof d.distance_cm !== "number") throw new Error("distance_cm must be a number or null");
  if (d.echo_valid && (typeof d.distance_cm !== "number" || d.distance_cm <= 0 || d.distance_cm > 450)) {
    throw new Error("Valid echo must contain a distance between 0 and 450 cm");
  }
  return value as SensorMessage;
}
