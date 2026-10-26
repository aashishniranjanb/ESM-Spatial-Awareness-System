# ESM Real-Time Vision, Tracking & Path Awareness Specification

## 1. Subsystem Architecture

```
+-----------------------------------------------------------------------------------------------+
| BROWSER WEBCAM CLIENT                                                                         |
| - getUserMedia (Laptop Camera)                                                                |
| - Offscreen Canvas Capture (320x240 @ ~8-10 FPS)                                              |
| - Binary WebSocket Packaging (8-byte header: frame_id + timestamp_ms + JPEG payload)          |
+-----------------------------------------------------------------------------------------------+
                                             |
                                             v  Binary WebSocket frame over ws://localhost:8000/ws
+-----------------------------------------------------------------------------------------------+
| FASTAPI BACKEND EVENT ROUTER (backend/app/websocket/ws_router.py)                             |
| - Bounded Queue & Rate Limiter (discards frames arriving faster than 100ms / 10 FPS)          |
| - ThreadPoolExecutor worker offloading (prevents blocking async event loop)                   |
+-----------------------------------------------------------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------------+
| OPENCV & ULTRALYTICS YOLO PIPELINE (backend/app/vision/yolo_pipeline.py)                      |
| - cv2.imdecode & dimension extraction                                                         |
| - YOLOv8n object detection & tracking (persistent track IDs)                                  |
| - Normalized Bounding Box translation [0.0, 1.0]                                              |
| - Latency & rolling FPS measurement                                                           |
+-----------------------------------------------------------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------------+
| PATH-AWARENESS & SENSOR ASSOCIATION ENGINES                                                   |
| - PathAwarenessAnalyzer (backend/app/vision/path_analyzer.py):                                |
|   - Forward path corridor intersection test                                                   |
|   - Physical obstacle classification (person, chair, table, etc.)                             |
| - SensorVisionAssociationEngine (backend/app/vision/association.py):                          |
|   - Heuristic acoustic cone correlation (~15-degree ultrasonic field)                         |
|   - Attaches experimental distance candidate without overriding ground-truth sensor reading   |
+-----------------------------------------------------------------------------------------------+
                                             |
                                             v  Broadcast JSON event 'vision.detection'
+-----------------------------------------------------------------------------------------------+
| FRONTEND VISUAL OVERLAY (src/components/camera-panel.tsx)                                     |
| - Visual path corridor overlay (dashed cyan boundary)                                         |
| - Color-coded bounding boxes:                                                                 |
|   - Red: PATH OBSTRUCTION                                                                     |
|   - Amber: IN CORRIDOR                                                                        |
|   - Purple: PERIPHERAL / OUTSIDE PATH                                                         |
| - Track ID tags (#1, #2), confidence score %, and ultrasonic echo estimates                   |
| - Detected Path Entities list with real-time classification                                   |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. Shared WebSocket Event Protocol (Extended)

### `vision.frame` (Client to Server - Binary)
8-byte header followed by standard JPEG bytes:
- Bytes 0-3: `uint32` Little-Endian `frame_id`
- Bytes 4-7: `uint32` Little-Endian `timestamp_ms`
- Bytes 8+: `uint8[]` JPEG image data

### `vision.detection` (Server to Client - JSON)
```json
{
  "event": "vision.detection",
  "session_id": "session-uuid-v4",
  "payload": {
    "frame_id": 14205,
    "detections": [
      {
        "id": "det-14205-0",
        "class_name": "chair",
        "class_id": 56,
        "confidence": 0.88,
        "box_normalized": { "x": 0.35, "y": 0.42, "w": 0.28, "h": 0.45 },
        "track_id": 1,
        "overlaps_path_corridor": true,
        "corridor_overlap_ratio": 0.72,
        "is_path_obstruction": true,
        "uncertainty": 0.12,
        "latency_ms": 38.5,
        "acoustic_candidate_dist_m": 1.42,
        "provenance": "estimated"
      }
    ],
    "latency_ms": 38.5,
    "status": {
      "model_name": "yolov8n.pt",
      "model_ready": true,
      "device": "cpu",
      "processed_fps": 9.4,
      "avg_latency_ms": 38.5
    }
  }
}
```

### `vision.config` (Client to Server - JSON)
```json
{
  "event": "vision.config",
  "session_id": "session-uuid-v4",
  "payload": {
    "conf_thresh": 0.40,
    "iou_thresh": 0.45
  }
}
```

---

## 3. Data Integrity & Scientific Grounding

> [!IMPORTANT]
> 1. **No Ground Truth Claims:** Bounding boxes and confidence scores are model predictions, not certified safety guarantees.
> 2. **Visual Path Corridor:** The forward path corridor is a visual assistance aid and not a collision-certified route planner.
> 3. **Sensor Association Heuristics:** Because a single HC-SR04 ultrasonic transducer emits a wide conical beam ($\approx 15^\circ$), individual optical detections are not claimed as definitive targets; correlated distances are labelled as `heuristic / candidate`.
