# ESM Visual SLAM Evaluation Report

**Document Version:** 1.0  
**Evaluation Date:** October 2026  
**Hardware Platform:** Windows 11, Python 3.13, ESP32 + HC-SR04 + MPU6050  
**Camera Source:** Laptop webcam at 320×240 via browser WebSocket

---

## 1. Executive Summary

ESM requires a visual SLAM (Simultaneous Localization and Mapping) backend to produce metrically grounded camera poses and 3D map points from the laptop webcam feed. This document evaluates candidate engines and documents the current integration status.

**Current status: No SLAM engine is installed.** The ESM backend provides a documented `SLAMBackend` interface and an honest `UnavailableSLAMBackend` that reports this state explicitly. The interface is ready for integration when a compatible engine becomes available.

> [!IMPORTANT]
> ESM does **not** claim that SLAM is active, does **not** generate fake camera poses or map points, and does **not** label heuristic projections as SLAM outputs. All spatial estimates are correctly classified by provenance.

---

## 2. Candidate Engine Evaluation

### 2.1 ORB-SLAM3

| Attribute | Detail |
|-----------|--------|
| **Authors** | Carlos Campos et al. (Universidad de Zaragoza) |
| **License** | GPLv3 |
| **Modes** | Monocular, Stereo, RGB-D, Mono-Inertial, Stereo-Inertial |
| **Language** | C++17 |
| **Dependencies** | OpenCV 4.x, Eigen3, Pangolin, DBoW2 (bundled), g2o (bundled) |
| **Repository** | https://github.com/UZ-SLAMLab/ORB_SLAM3 |

**Capabilities:**
- State-of-the-art feature-based SLAM with loop closure and multi-map
- Visual-inertial mode could fuse MPU6050 IMU data for metric scale
- Produces keyframes, 3D map points, and 6-DOF camera trajectory

**Windows Compatibility:**
- Designed and tested exclusively for Ubuntu Linux
- Native Windows build requires MSVC 2022, manual CMake configuration for every dependency
- Pangolin visualization library has limited Windows support
- **No pip-installable Python bindings exist for Windows**
- Community `orbslam3-python` packages ship Linux-only `.so` wheels
- Realistic Windows path: Docker Desktop with WSL2, or manual MSVC compilation

**Integration Requirements:**
- C++ library compiled as shared library (`.dll` on Windows, `.so` on Linux)
- Python bindings via pybind11 wrapping the C++ `System`, `Frame`, and `MapPoint` classes
- Frame submission via buffer sharing or file-descriptor passing
- Thread-safe extraction of camera pose and map point arrays

**Assessment:** Excellent SLAM quality, but impractical for direct `pip install` integration on Windows. Requires either WSL2/Docker or dedicated native build effort. GPLv3 license has distribution implications.

### 2.2 Stella-VSLAM (Fork of OpenVSLAM)

| Attribute | Detail |
|-----------|--------|
| **License** | BSD-2-Clause |
| **Modes** | Monocular, Stereo, RGB-D |
| **Language** | C++ |
| **Dependencies** | OpenCV, Eigen3, g2o, DBoW2, yaml-cpp, spdlog |
| **Repository** | https://github.com/stella-cv/stella_vslam |

**Assessment:** BSD license is preferable. Same C++ native dependency challenge as ORB-SLAM3. No Python bindings on PyPI. Community Docker images exist for Linux.

### 2.3 pySLAM (Python Framework)

| Attribute | Detail |
|-----------|--------|
| **License** | MIT |
| **Language** | Python with C++ optimization helpers |
| **Repository** | https://github.com/luigifreda/pyslam |

**Assessment:** Python-first modular framework supporting multiple feature extractors (ORB, SuperPoint, LightGlue). Closest to pip-installable, but still requires C++ helper compilation for pose graph optimization (g2o wrappers). Best candidate for future integration. Does not yet provide a clean single-command install.

### 2.4 Lightweight Python SLAM Implementations

- **vSLAM-py** (Gongsta): Pure Python visual odometry. Educational quality, no loop closure.
- **Fosowl/monocularSlam**: Lightweight single-file SLAM. No production-grade optimization.
- **opencv-SimpleSLAM** (KlrShaK): OpenCV + LightGlue features. Research prototype.

**Assessment:** Suitable for educational exploration. Not production-grade for persistent spatial mapping.

### 2.5 OpenCV Feature Tracking + Essential Matrix (Current Capability)

ESM's current environment already has OpenCV installed. A lightweight visual odometry pipeline using:
- ORB or SIFT feature extraction
- Optical flow tracking (Lucas-Kanade)
- Essential matrix decomposition for relative pose
- Triangulation for 3D point recovery

This provides relative motion estimation without external native dependencies. However, it does **not** constitute SLAM — there is no loop closure, no global optimization, and no persistent map management. It should be labeled "visual odometry" not "SLAM."

---

## 3. Monocular Scale Ambiguity

Monocular visual SLAM recovers camera motion and 3D structure **up to an unknown scale factor**. The reconstructed map is geometrically correct but could be 10× too large or 10× too small.

**Why:** A single camera cannot distinguish between a large object far away and a small object nearby. The essential matrix decomposition yields direction but not magnitude.

**Scale sources available in ESM:**

| Source | Type | Precision | Notes |
|--------|------|-----------|-------|
| HC-SR04 ultrasonic | Direct measurement | ±1 cm at short range | Forward-only, 15° beam, 2–400 cm |
| MPU6050 accelerometer | Indirect (double integration) | Poor (drift) | Not viable for standalone scale |
| Known object sizes | Semantic | Variable | Requires object detection + size database |
| IMU-camera fusion (VIO) | Sensor fusion | Good with calibration | Requires ORB-SLAM3 inertial mode |

**ESM approach:** When a SLAM engine provides map points, the HC-SR04 ultrasonic distance can be used to set metric scale by correlating the measured range with a SLAM-estimated depth along the forward axis. This requires explicit calibration and is marked as "estimated" provenance.

---

## 4. SLAM Backend Interface Contract

ESM defines a replaceable `SLAMBackend` abstract class in `backend/app/mapping/slam_interface.py`:

```python
class SLAMBackend(abc.ABC):
    def get_name(self) -> str: ...
    def get_status(self) -> SLAMStatus: ...
    def is_available(self) -> bool: ...
    def initialize(self, config: Dict) -> bool: ...
    def process_frame(self, image_bytes, frame_id, timestamp_ms) -> Optional[CameraPose]: ...
    def get_map_points(self) -> List[MapPoint3D]: ...
    def get_trajectory(self) -> List[CameraPose]: ...
    def reset(self) -> None: ...
    def shutdown(self) -> None: ...
    def set_scale(self, scale_factor, source) -> None: ...
```

**States tracked:**
- `NOT_INITIALIZED` — Engine loaded but not yet processing
- `INITIALIZING` — Collecting initial frames for feature triangulation
- `TRACKING` — Actively tracking camera pose
- `TRACKING_LOST` — Lost visual features, attempting relocalization
- `RELOCALIZATION` — Re-localizing in existing map
- `UNAVAILABLE` — No engine installed (current state)

**Current implementation:** `UnavailableSLAMBackend` returns `is_available() = False`, `process_frame() = None`, empty map points, and an explicit error message. It does not fabricate any outputs.

---

## 5. Integration Path

When a SLAM engine becomes available (e.g., via WSL2 Docker container or native pySLAM installation):

1. Implement a new class extending `SLAMBackend` (e.g., `ORBSlam3Backend` or `PySLAMBackend`)
2. Initialize the engine with camera intrinsics from `MapCalibration`
3. Feed frames from the existing binary WebSocket transport to `process_frame()`
4. Publish `CameraPose` results as `map.update` WebSocket events
5. Use ultrasonic measurements to calibrate scale via `set_scale()`
6. Persist trajectory and map points in the session database

The frontend `ScanViewer` already renders persistent landmarks and camera trajectory from `map.update` events — no additional frontend changes are needed for basic SLAM visualization.

---

## 6. Limitations and Honest Assessment

| Claim | Status |
|-------|--------|
| SLAM is active | **No** — no engine is installed |
| Camera poses are estimated | **No** — only dead-reckoning from IMU gyroscope |
| Map points come from SLAM | **No** — all 3D points come from ultrasonic echoes (measured) or acoustic-correlated YOLO detections (estimated) |
| Metric scale is available | **Partial** — ultrasonic provides metric distance in the forward direction only |
| Monocular depth is trustworthy | **No** — monocular SLAM cannot provide metric depth without external calibration |

All spatial data in ESM carries explicit provenance tags (`measured`, `estimated`, `illustrative`) to prevent misinterpretation.
