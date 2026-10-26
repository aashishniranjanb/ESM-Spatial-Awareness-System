# ESM — Spatial Awareness System

**ESM (formerly EchoMap)** is a production-oriented assistive spatial-awareness research platform uniting an **ESP32 Dev Module (HC-SR04 ultrasonic rangefinder + MPU6050 6-DOF IMU)** with a **Next.js 14 + React Three Fiber 3D spatial workspace**, **OpenCV + YOLOv8 laptop webcam perception**, and an asynchronous **Python FastAPI + SQLite persistence backend**.

> [!WARNING]
> **Safety Disclaimer:** ESM is an assistive-technology research prototype, **not a certified mobility aid**. A single ultrasonic beam and monocular webcam cannot reconstruct room geometries or provide reliable autonomous road navigation. Always keep established mobility aids in active use.

---

## 1. System Architecture

```mermaid
flowchart TD
    subgraph Hardware Layer
        ESP32[ESP32 Dev Module]
        HCSR04[HC-SR04 Ultrasonic] -->|TRIG/ECHO| ESP32
        MPU6050[MPU6050 6-DOF IMU] -->|I2C| ESP32
    end

    subgraph Browser Client (Next.js 14)
        ESP32 -->|USB Web Serial @ 115200| WebSerial[Web Serial Driver]
        Webcam[Laptop Camera / MediaDevices] -->|Canvas Frame Grab 320x240| CamPanel[Camera Overlay Panel]
        WebSerial --> PageCore[ESM Frontend Coordinator]
        PageCore --> R3F[Three.js 3D Viewport & Human Avatar]
        PageCore --> WSClient[Backend WebSocket Client]
        CamPanel -->|Binary Frame Packets| WSClient
    end

    subgraph Backend Subsystem (FastAPI)
        WSClient <-->|WebSocket Text & Binary /ws| WSRouter[WebSocket Router]
        WSRouter --> FrameWorker[ThreadPoolExecutor Worker]
        FrameWorker --> YOLO[OpenCV + YOLOv8 Detection & Tracking]
        YOLO --> PathCorridor[Path Corridor Analyzer]
        PathCorridor --> Assoc[Acoustic-Vision Heuristic Assoc]
        Assoc -->|vision.detection| WSRouter
        WSRouter --> SpatialPipe[Spatial Transform Pipeline]
        SpatialPipe -->|spatial.point| WSRouter
        WSRouter --> DB[(SQLite echomap.db)]
        REST[FastAPI REST API /api/v1/sessions] --> DB
    end
```

---

## 2. Quick Start (Windows PowerShell)

### Prerequisites
- Node.js 20+ LTS
- Python 3.11+ (Python 3.13 in `.\venv`)
- Google Chrome or Microsoft Edge (for Web Serial API support)

### Option A: Run Both Services via PowerShell Script
```powershell
.\start_echomap.ps1
```

### Option B: Manual Startup

**Terminal 1 — FastAPI Backend:**
```powershell
$env:PYTHONPATH="backend"
.\venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```
- API Docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- WebSocket Endpoint: `ws://127.0.0.1:8000/ws`

**Terminal 2 — Next.js Frontend:**
```powershell
npm run dev
```
- Open `http://localhost:3000` in your browser.

---

## 3. Hardware Wiring Checklist

| Sensor Pin | ESP32 GPIO | Electrical Notes |
|---|---|---|
| **HC-SR04 VCC** | 5V / VIN | Ensure adequate 5V power supply |
| **HC-SR04 GND** | GND | Common ground with ESP32 |
| **HC-SR04 TRIG** | GPIO 5 | 3.3V logic output from ESP32 |
| **HC-SR04 ECHO** | GPIO 18 | **Must use resistor voltage divider** (5V -> 3.3V) |
| **MPU6050 VCC** | 3.3V | Standard 3.3V rail |
| **MPU6050 GND** | GND | Common ground |
| **MPU6050 SDA** | GPIO 21 | Hardware I2C Data |
| **MPU6050 SCL** | GPIO 22 | Hardware I2C Clock |

Firmware is located in: `firmware/EchoMap_ESP32_Level2/EchoMap_ESP32_Level2.ino`. Flash via Arduino IDE at 115200 baud.

---

## 4. Key Architectural Features

1. **Three-Tier Provenance Classification:**
   - **MEASURED:** Grounded ultrasonic returns ($2\text{ cm} \le d \le 400\text{ cm}$) rendered as color-banded depth points.
   - **ESTIMATED:** Derived spatial coordinates, yaw/pitch integration, and optical YOLO object bounds. Monocular detections never claim ground-truth physical depth.
   - **ILLUSTRATIVE:** 3D environment assets (curbs, chairs, tables, doors) and deterministic demo walkthrough fixtures.
2. **High-Throughput Binary Frame Protocol:**
   - 8-byte binary header (`frame_id`, `timestamp_ms`) followed by raw JPEG bytes transmitted directly over WebSocket.
   - Throttled processing ($\le 10\text{ FPS}$) executed on a dedicated CPU thread pool to protect real-time telemetry.
3. **Path Corridor Awareness:**
   - Dynamic central path corridor ($x \in [0.30, 0.70]$) overlaid on the camera feed.
   - Real-time classification of peripheral vs. path-obstructing objects with confidence and bounding box visualizations.
4. **Deterministic Demo Mode:**
   - Offline synthetic walkthrough with seeded pseudo-random sensor measurements, avatar rotation, and simulated obstacles. Works completely independent of physical hardware.
5. **Persistent Sessions & Ordered Replay:**
   - Durable SQLite storage for sessions, samples, spatial points, and vision detections.
   - Session replay endpoint (`GET /api/v1/sessions/{id}/replay`) and UI control to playback recorded events in timestamp order.

---

## 5. Verification & Testing

### Run Backend Pytest Suite:
```powershell
$env:PYTHONPATH="backend"
.\venv\Scripts\pytest backend\tests -o asyncio_mode=auto
```
All **13 integration and unit tests** pass cleanly:
- Session lifecycle & persistence (`test_sessions.py`)
- Spatial transformations, OpenGL coordinates, spike filter (`test_spatial.py`)
- YOLO pipeline, corridor overlap, acoustic-vision association (`test_vision.py`)
- WebSocket ping/pong, binary frame transport, sample broadcast, replay stream (`test_websocket_integration.py`)

### Run Frontend Production Build:
```powershell
npm run build
```
Static bundle compiled successfully (`exit code 0`).
