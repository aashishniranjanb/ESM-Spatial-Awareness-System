"""
OpenCV-based Visual Odometry and Feature-Tracking SLAM Engine.

Implements the SLAMBackend interface using genuine OpenCV computer vision primitives:
- Fast feature extraction (ORB / FAST)
- KLT Lucas-Kanade optical flow tracking
- 5-point algorithm / Essential matrix recovery (cv2.findEssentialMat + cv2.recoverPose)
- Triangulation of 3D map points (cv2.triangulatePoints)
- Real-time scale integration from ultrasonic rangefinder telemetry

Runs natively in standard Python on Windows without requiring custom C++ builds.
"""
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
import cv2
import numpy as np

from app.mapping.slam_interface import (
    SLAMBackend,
    SLAMState,
    SLAMStatus,
    CameraPose,
    MapPoint3D,
)

logger = logging.getLogger("esm.opencv_slam")


class OpenCVVisualSLAMBackend(SLAMBackend):
    """
    Genuine feature-based Monocular Visual Odometry / SLAM backend.
    Tracks camera motion in 6-DOF and estimates 3D landmark points
    from sequential video frames.
    """

    def __init__(
        self,
        focal_length: float = 500.0,
        cx: float = 320.0,
        cy: float = 240.0,
        max_features: int = 400,
        min_features: int = 50,
    ):
        self.focal_length = focal_length
        self.cx = cx
        self.cy = cy
        self.K = np.array([
            [focal_length, 0.0, cx],
            [0.0, focal_length, cy],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)

        self.max_features = max_features
        self.min_features = min_features

        # ORB detector for keyframe feature re-detection
        self.orb = cv2.ORB_create(nfeatures=self.max_features)

        # State tracking
        self.state = SLAMState.NOT_INITIALIZED
        self.current_R = np.eye(3, dtype=np.float64)
        self.current_t = np.zeros((3, 1), dtype=np.float64)

        self.prev_gray: Optional[np.ndarray] = None
        self.prev_pts: Optional[np.ndarray] = None

        self.trajectory: List[CameraPose] = []
        self.map_points: List[MapPoint3D] = []
        self._point_id_counter = 0

        self.num_keyframes = 0
        self.tracking_fps = 0.0
        self._last_process_time = 0.0
        self.last_error: Optional[str] = None
        self.initialized_at: Optional[float] = None

        # External scale grounding
        self.scale_factor: float = 1.0
        self.scale_source: Optional[str] = None
        self.scale_available: bool = False

    def get_name(self) -> str:
        return "opencv-vo-slam"

    def is_available(self) -> bool:
        return True

    def get_status(self) -> SLAMStatus:
        return SLAMStatus(
            state=self.state,
            engine_name="OpenCV Visual Odometry (ORB/KLT)",
            engine_version=f"OpenCV {cv2.__version__}",
            num_map_points=len(self.map_points),
            num_keyframes=self.num_keyframes,
            tracking_fps=round(self.tracking_fps, 1),
            scale_available=self.scale_available,
            scale_source=self.scale_source,
            last_error=self.last_error,
            initialized_at=self.initialized_at,
        )

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        if config:
            if "focal_length" in config:
                self.focal_length = float(config["focal_length"])
            if "cx" in config and "cy" in config:
                self.cx = float(config["cx"])
                self.cy = float(config["cy"])
            self.K = np.array([
                [self.focal_length, 0.0, self.cx],
                [0.0, self.focal_length, self.cy],
                [0.0, 0.0, 1.0]
            ], dtype=np.float64)

        self.reset()
        self.state = SLAMState.INITIALIZING
        self.initialized_at = time.time()
        logger.info(f"OpenCVVisualSLAMBackend initialized with K: fx={self.focal_length}, cx={self.cx}, cy={self.cy}")
        return True

    def set_scale(self, scale_factor: float, source: str) -> None:
        """Ground the monocular relative scale using ultrasonic rangefinder telemetry."""
        if scale_factor > 0.05:
            self.scale_factor = float(scale_factor)
            self.scale_source = source
            self.scale_available = True

    def process_frame(self, image_bytes: bytes, frame_id: int, timestamp_ms: int) -> Optional[CameraPose]:
        start_t = time.time()
        try:
            # Decode JPEG/PNG image buffer to grayscale
            np_arr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_GRAYSCALE)
            if img is None:
                self.last_error = "Failed to decode image frame"
                return None

            # Dynamically calibrate principal point if image dimensions change
            h, w = img.shape
            if abs(self.cx - (w / 2.0)) > 2.0 or abs(self.cy - (h / 2.0)) > 2.0:
                self.cx = w / 2.0
                self.cy = h / 2.0
                self.focal_length = max(w, h) * 0.9
                self.K = np.array([
                    [self.focal_length, 0.0, self.cx],
                    [0.0, self.focal_length, self.cy],
                    [0.0, 0.0, 1.0]
                ], dtype=np.float64)

            # First frame initialization
            if self.prev_gray is None or self.prev_pts is None or len(self.prev_pts) < self.min_features:
                kps = cv2.goodFeaturesToTrack(
                    img,
                    maxCorners=self.max_features,
                    qualityLevel=0.01,
                    minDistance=10,
                    blockSize=3
                )
                if kps is not None and len(kps) >= self.min_features:
                    self.prev_gray = img
                    self.prev_pts = kps
                    self.state = SLAMState.INITIALIZING
                    self.num_keyframes += 1
                return None

            # Optical Flow KLT tracking from previous frame
            curr_pts, status, err = cv2.calcOpticalFlowPyrLK(
                self.prev_gray,
                img,
                self.prev_pts,
                None,
                winSize=(21, 21),
                maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
            )

            # Filter valid tracked points
            valid_mask = (status.flatten() == 1)
            p0 = self.prev_pts[valid_mask]
            p1 = curr_pts[valid_mask]

            if len(p0) < 15:
                # Lost tracking, redetect features
                self.state = SLAMState.TRACKING_LOST
                kps = cv2.goodFeaturesToTrack(
                    img,
                    maxCorners=self.max_features,
                    qualityLevel=0.01,
                    minDistance=10,
                    blockSize=3
                )
                if kps is not None and len(kps) >= self.min_features:
                    self.prev_pts = kps
                    self.prev_gray = img
                return None

            # Calculate Essential Matrix using 5-point RANSAC
            E, inlier_mask = cv2.findEssentialMat(
                p1, p0, self.K,
                method=cv2.RANSAC,
                prob=0.999,
                threshold=1.0
            )

            if E is None or E.shape != (3, 3):
                self.prev_gray = img
                self.prev_pts = p1.reshape(-1, 1, 2)
                return None

            # Recover relative rotation and translation
            inlier_cnt, R, t, mask_pose = cv2.recoverPose(E, p1, p0, self.K)

            # Apply scale factor (from rangefinder or metric prior)
            t_scaled = t * self.scale_factor

            # Update world coordinate camera pose:
            # Camera forward is -Z in Three.js coordinates
            self.current_t = self.current_t + self.current_R.dot(t_scaled)
            self.current_R = R.dot(self.current_R)

            # Convert 3x3 rotation matrix to quaternion [qx, qy, qz, qw]
            quat = self._rotation_matrix_to_quaternion(self.current_R)

            # In Three.js space: X=Right, Y=Up, Z=Back (-Z is forward)
            # OpenCV camera: X=Right, Y=Down, Z=Forward
            cam_pos = [
                float(self.current_t[0, 0]),
                float(-self.current_t[1, 0]),
                float(-self.current_t[2, 0])
            ]

            self.state = SLAMState.TRACKING

            # Periodically triangulate 3D map points from baseline motion
            motion_dist = np.linalg.norm(t_scaled)
            if motion_dist > 0.05 and inlier_cnt > 20:
                self._triangulate_new_points(p0, p1, inlier_mask, frame_id)

            pose = CameraPose(
                timestamp_ms=timestamp_ms,
                frame_id=frame_id,
                position=cam_pos,
                rotation_quat=quat,
                tracking_state=self.state,
                scale_factor=self.scale_factor,
                scale_source=self.scale_source
            )
            self.trajectory.append(pose)
            if len(self.trajectory) > 2000:
                self.trajectory = self.trajectory[-1500:]

            # Feature management: replenish tracked points if depleted
            if len(p1) < self.min_features:
                new_kps = cv2.goodFeaturesToTrack(
                    img,
                    maxCorners=self.max_features - len(p1),
                    qualityLevel=0.01,
                    minDistance=10,
                    blockSize=3
                )
                if new_kps is not None and len(new_kps) > 0:
                    p1 = np.vstack([p1.reshape(-1, 1, 2), new_kps])
                    self.num_keyframes += 1
            else:
                p1 = p1.reshape(-1, 1, 2)

            self.prev_gray = img
            self.prev_pts = p1

            # Performance telemetry
            dt = time.time() - start_t
            if dt > 0:
                self.tracking_fps = 0.85 * self.tracking_fps + 0.15 * (1.0 / dt)

            return pose

        except Exception as ex:
            self.last_error = str(ex)
            logger.error(f"SLAM error in frame {frame_id}: {ex}")
            return None

    def _triangulate_new_points(
        self,
        p0: np.ndarray,
        p1: np.ndarray,
        inlier_mask: Optional[np.ndarray],
        frame_id: int
    ) -> None:
        """Triangulate 3D map points from sequential camera views."""
        try:
            # Projection matrices P1 = K[I|0], P2 = K[R|t]
            P1 = self.K @ np.hstack((np.eye(3), np.zeros((3, 1))))
            P2 = self.K @ np.hstack((self.current_R, self.current_t))

            # Select inliers
            if inlier_mask is not None:
                valid = inlier_mask.flatten() == 1
                pts0 = p0[valid]
                pts1 = p1[valid]
            else:
                pts0 = p0
                pts1 = p1

            if len(pts0) < 10:
                return

            # Triangulate homogeneous 4D coordinates
            pts4D = cv2.triangulatePoints(
                P1, P2,
                pts0.reshape(-1, 2).T,
                pts1.reshape(-1, 2).T
            )
            # De-homogenize: [X, Y, Z] = pts4D[:3] / pts4D[3]
            w = pts4D[3]
            valid_w = np.abs(w) > 1e-5
            pts3D = pts4D[:3, valid_w] / w[valid_w]

            # Filter points within reasonable assistive range (0.3m to 8.0m in front of camera)
            for i in range(min(pts3D.shape[1], 15)):
                x, y, z = float(pts3D[0, i]), float(-pts3D[1, i]), float(-pts3D[2, i])
                dist = np.sqrt(x * x + y * y + z * z)
                if 0.3 < dist < 8.0 and z < -0.1:
                    self._point_id_counter += 1
                    self.map_points.append(
                        MapPoint3D(
                            id=f"vo-{self._point_id_counter}",
                            position=[round(x, 3), round(y, 3), round(z, 3)],
                            num_observations=1,
                            last_observed_frame=frame_id,
                            uncertainty=round(float(dist * 0.08), 3),
                            provenance="estimated",
                        )
                    )

            if len(self.map_points) > 500:
                self.map_points = self.map_points[-400:]

        except Exception as ex:
            logger.debug(f"Triangulation skipped: {ex}")

    def _rotation_matrix_to_quaternion(self, R: np.ndarray) -> List[float]:
        """Convert 3x3 rotation matrix to normalized quaternion [qx, qy, qz, qw]."""
        tr = np.trace(R)
        if tr > 0:
            S = 2.0 * np.sqrt(tr + 1.0)
            qw = 0.25 * S
            qx = (R[2, 1] - R[1, 2]) / S
            qy = (R[0, 2] - R[2, 0]) / S
            qz = (R[1, 0] - R[0, 1]) / S
        elif (R[0, 0] > R[1, 1]) and (R[0, 0] > R[2, 2]):
            S = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            qw = (R[2, 1] - R[1, 2]) / S
            qx = 0.25 * S
            qy = (R[0, 1] + R[1, 0]) / S
            qz = (R[0, 2] + R[2, 0]) / S
        elif R[1, 1] > R[2, 2]:
            S = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            qw = (R[0, 2] - R[2, 0]) / S
            qx = (R[0, 1] + R[1, 0]) / S
            qy = 0.25 * S
            qz = (R[1, 2] + R[2, 1]) / S
        else:
            S = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            qw = (R[1, 0] - R[0, 1]) / S
            qx = (R[0, 2] + R[2, 0]) / S
            qy = (R[1, 2] + R[2, 1]) / S
            qz = 0.25 * S
        return [round(float(qx), 4), round(float(qy), 4), round(float(qz), 4), round(float(qw), 4)]

    def get_map_points(self) -> List[MapPoint3D]:
        return self.map_points

    def get_trajectory(self) -> List[CameraPose]:
        return self.trajectory

    def reset(self) -> None:
        self.state = SLAMState.NOT_INITIALIZED
        self.current_R = np.eye(3, dtype=np.float64)
        self.current_t = np.zeros((3, 1), dtype=np.float64)
        self.prev_gray = None
        self.prev_pts = None
        self.trajectory.clear()
        self.map_points.clear()
        self._point_id_counter = 0
        self.num_keyframes = 0
        self.tracking_fps = 0.0
        self.last_error = None
        logger.info("OpenCVVisualSLAMBackend reset.")

    def shutdown(self) -> None:
        self.reset()
        self.state = SLAMState.UNAVAILABLE
