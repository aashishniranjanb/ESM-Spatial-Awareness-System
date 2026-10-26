# ESM WebSocket Protocol Specification

**Protocol Version:** 2.0 (Part 3 End-to-End Hardened)  
**Transports:**
- JSON-encoded WebSocket text frames for telemetry, status, commands, and replay
- High-throughput binary frame packets for camera video ingestion
**Endpoint:** `/ws/{session_id}` (or `/ws/global`)

---

## 1. Binary Frame Transport (Webcam Ingestion)

For high-throughput frame transmission without base64 overhead, the frontend sends binary packets directly over the WebSocket:

- **Header (8 Bytes, Little-Endian):**
  - Bytes 0–3: `uint32` `frame_id` (Monotonically increasing counter)
  - Bytes 4–7: `uint32` `timestamp_ms` (Browser client epoch timestamp in ms)
- **Payload (Remaining Bytes):**
  - Binary raw JPEG buffer from offscreen canvas snapshot (320×240)

### Processing & Throttling
- The FastAPI WebSocket worker decodes headers with `struct.unpack("<II", bin_data[:8])`.
- Backpressure policy: Drops frames if the previous processed frame was $< 100\text{ ms}$ ago ($\le 10\text{ FPS}$).
- Inference is offloaded onto a background `ThreadPoolExecutor` to avoid blocking the asyncio event loop.

---

## 2. Text Event Types

### `ping` / `pong` (Heartbeat)
- **Client to Server:** `{"event": "ping", "timestamp": 1713098400000}`
- **Server to Client:** `{"event": "pong", "timestamp": 1713098400000}`
The frontend client maintains a 15-second heartbeat timer with exponential backoff reconnection.

### `sensor.sample`
Forwarded from the browser's Web Serial stream to the backend.
```json
{
  "event": "sensor.sample",
  "session_id": "session-uuid-v4",
  "payload": {
    "v": 1,
    "type": "sample",
    "ts_ms": 123456,
    "distance_cm": 82.4,
    "echo_valid": true,
    "accel_m_s2": { "x": 0.1, "y": 9.8, "z": 0.2 },
    "gyro_rad_s": { "x": 0.01, "y": -0.02, "z": 0.0 }
  }
}
```

### `spatial.point`
Emitted by the backend pipeline when a sample is accepted and projected into the relative coordinate frame ($+X$ right, $+Y$ up, $-Z$ forward).
```json
{
  "event": "spatial.point",
  "session_id": "session-uuid-v4",
  "payload": {
    "id": "123456-0",
    "ts_ms": 123456,
    "x": 0.12,
    "y": 0.04,
    "z": -0.82,
    "distance": 0.824,
    "intensity": 0.794,
    "uncertainty": 0.0465,
    "quality_flag": "measured"
  }
}
```

### `vision.detection`
Emitted when OpenCV/YOLO processes a binary frame or base64 frame.
```json
{
  "event": "vision.detection",
  "session_id": "session-uuid-v4",
  "payload": {
    "frame_id": 42,
    "detections": [
      {
        "id": "det-1",
        "frame_id": 42,
        "timestamp_ms": 123456,
        "class_name": "chair",
        "class_id": 56,
        "confidence": 0.89,
        "box_normalized": { "x": 0.40, "y": 0.45, "w": 0.20, "h": 0.40 },
        "track_id": 1,
        "overlaps_path_corridor": true,
        "corridor_overlap_ratio": 0.75,
        "is_path_obstruction": true,
        "is_approximate": true,
        "uncertainty": 0.15,
        "acoustic_candidate_dist_m": 0.85,
        "provenance": "estimated"
      }
    ],
    "latency_ms": 32.4,
    "status": {
      "model_name": "yolov8n.pt",
      "model_ready": true,
      "device": "cpu",
      "processed_fps": 9.4,
      "avg_latency_ms": 34.1
    }
  }
}
```

### `vision.status`
Emitted on initial connection or when vision pipeline configuration changes:
```json
{
  "event": "vision.status",
  "session_id": "global",
  "payload": {
    "model_name": "yolov8n.pt",
    "model_ready": true,
    "device": "cpu",
    "input_size": 320,
    "confidence_threshold": 0.35,
    "iou_threshold": 0.45,
    "tracking_enabled": true,
    "processed_fps": 9.5,
    "avg_latency_ms": 33.2
  }
}
```

### `vision.config`
Sent from frontend to calibrate YOLO thresholds or central corridor geometry dynamically:
```json
{
  "event": "vision.config",
  "session_id": "global",
  "payload": {
    "conf_thresh": 0.40,
    "iou_thresh": 0.45,
    "corridor": {
      "x_min": 0.30,
      "x_max": 0.70,
      "y_min": 0.35,
      "y_max": 1.00
    }
  }
}
```

---

## 3. Session Replay API

Endpoint: `GET /api/v1/sessions/{session_id}/replay`

Returns a unified, chronologically interleaved event sequence:
```json
{
  "session": {
    "id": "uuid",
    "name": "Corridor sweep",
    "source_mode": "hardware",
    "status": "created",
    "sample_count": 42,
    "point_count": 40,
    "created_at": "2026-10-26T12:00:00Z"
  },
  "event_count": 82,
  "events": [
    {
      "type": "sensor.sample",
      "timestamp_ms": 1000,
      "data": { ... }
    },
    {
      "type": "spatial.point",
      "timestamp_ms": 1000,
      "data": { ... }
    },
    {
      "type": "vision.detection",
      "timestamp_ms": 1100,
      "data": { ... }
    }
  ]
}
```
The frontend iterates through this stream in timestamp order to accurately reconstruct the past environment scan.
