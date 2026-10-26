"""
Persistent spatial map model for ESM.

Manages:
- Landmarks: persistent 3D points from various sources (ultrasonic, SLAM, vision+depth)
- Object tracks: tracked YOLO detections with stable IDs across frames  
- Camera poses: trajectory from SLAM or dead-reckoning
- Coordinate frame transforms between SLAM frame and ESM scene frame
- Calibration metadata
- Provenance classification: measured, estimated, illustrative

Key invariants:
- Landmarks persist across frames. They are NOT cleared on each camera frame.
- Each landmark has a stable ID derived from its source (track_id, point_id, etc.)
- Stale landmarks are marked stale after N frames without observation, not deleted.
- Map reset is an explicit user action, not implicit.
"""
import time
import math
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("esm.mapping.map_state")

STALE_FRAME_THRESHOLD = 150  # Mark stale after ~15s at 10fps
MERGE_DISTANCE_THRESHOLD = 0.3  # metres

@dataclass
class Landmark:
    """A persistent 3D landmark in the ESM scene coordinate frame."""
    id: str
    x: float
    y: float
    z: float
    label: Optional[str] = None
    confidence: float = 0.5
    observation_count: int = 1
    first_observed_frame: int = 0
    last_observed_frame: int = 0
    first_observed_ms: int = 0
    last_observed_ms: int = 0
    uncertainty: float = 0.15
    provenance: str = "estimated"  # "measured", "estimated", "illustrative"
    source: str = "unknown"  # "ultrasonic", "vision_track", "slam_point"
    track_id: Optional[int] = None
    is_stale: bool = False
    has_valid_depth: bool = False  # True only when depth source is documented
    depth_source: Optional[str] = None  # "ultrasonic_echo", "slam_triangulation", None

@dataclass
class ObjectTrack:
    """A tracked object from YOLO with observations across frames."""
    track_id: int
    class_name: str
    class_id: int
    first_frame: int = 0
    last_frame: int = 0
    observation_count: int = 0
    # Latest 2D observation (normalized camera-space)
    last_box_normalized: Optional[Dict] = None
    last_confidence: float = 0.0
    # 3D position only if depth is available
    has_3d_position: bool = False
    position_3d: Optional[List[float]] = None
    depth_source: Optional[str] = None
    landmark_id: Optional[str] = None  # linked landmark if 3D is valid
    is_active: bool = True

@dataclass
class CoordinateTransform:
    """Transform between SLAM and ESM scene frames."""
    # 4x4 matrix flattened row-major (identity by default)
    slam_to_scene: List[float] = field(default_factory=lambda: [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0
    ])
    scale: float = 1.0
    source: str = "identity"  # "identity", "ultrasonic_calibration", "manual"

@dataclass
class MapCalibration:
    """Calibration metadata for the map."""
    camera_fov_h_deg: float = 65.0
    camera_fov_v_deg: float = 50.0
    camera_resolution: Tuple[int, int] = (320, 240)
    ultrasonic_beam_deg: float = 15.0
    ultrasonic_min_cm: float = 2.0
    ultrasonic_max_cm: float = 400.0
    imu_gyro_bias: Optional[List[float]] = None

class PersistentMapState:
    """
    In-memory persistent map that accumulates landmarks and tracks across frames.
    
    This is NOT cleared on each camera frame. Landmarks persist until:
    1. Explicitly removed by the user (map reset)
    2. Marked stale after STALE_FRAME_THRESHOLD frames without re-observation
    """
    
    def __init__(self, session_id: str = "global"):
        self.session_id = session_id
        self.landmarks: Dict[str, Landmark] = {}
        self.object_tracks: Dict[int, ObjectTrack] = {}
        self.camera_poses: List[Dict] = []  # Serializable pose dicts
        self.coordinate_transform = CoordinateTransform()
        self.calibration = MapCalibration()
        self.current_frame_id: int = 0
        self.current_timestamp_ms: int = 0
        self.created_at: float = time.time()
        self.last_updated_at: float = time.time()
        self._landmark_counter: int = 0
    
    def get_status(self) -> Dict:
        active_landmarks = sum(1 for lm in self.landmarks.values() if not lm.is_stale)
        stale_landmarks = sum(1 for lm in self.landmarks.values() if lm.is_stale)
        active_tracks = sum(1 for t in self.object_tracks.values() if t.is_active)
        
        return {
            "session_id": self.session_id,
            "total_landmarks": len(self.landmarks),
            "active_landmarks": active_landmarks,
            "stale_landmarks": stale_landmarks,
            "total_object_tracks": len(self.object_tracks),
            "active_object_tracks": active_tracks,
            "camera_pose_count": len(self.camera_poses),
            "current_frame_id": self.current_frame_id,
            "coordinate_transform_source": self.coordinate_transform.source,
            "created_at": self.created_at,
            "last_updated_at": self.last_updated_at,
        }
    
    def add_ultrasonic_landmark(self, point_id: str, x: float, y: float, z: float,
                                 distance_m: float, uncertainty: float,
                                 frame_id: int, timestamp_ms: int) -> Landmark:
        """Add or update a landmark from ultrasonic echo (MEASURED provenance)."""
        lm_id = f"us-{point_id}"
        
        # Check for nearby existing ultrasonic landmarks to merge
        existing = self._find_nearest_landmark(x, y, z, source="ultrasonic",
                                                max_distance=MERGE_DISTANCE_THRESHOLD)
        if existing:
            # Update existing landmark with new observation
            existing.x = (existing.x * existing.observation_count + x) / (existing.observation_count + 1)
            existing.y = (existing.y * existing.observation_count + y) / (existing.observation_count + 1)
            existing.z = (existing.z * existing.observation_count + z) / (existing.observation_count + 1)
            existing.observation_count += 1
            existing.last_observed_frame = frame_id
            existing.last_observed_ms = timestamp_ms
            existing.uncertainty = min(existing.uncertainty, uncertainty)
            existing.is_stale = False
            self.last_updated_at = time.time()
            return existing
        
        lm = Landmark(
            id=lm_id, x=x, y=y, z=z,
            label=f"Echo {distance_m:.2f}m",
            confidence=0.85,
            observation_count=1,
            first_observed_frame=frame_id, last_observed_frame=frame_id,
            first_observed_ms=timestamp_ms, last_observed_ms=timestamp_ms,
            uncertainty=uncertainty,
            provenance="measured",
            source="ultrasonic",
            has_valid_depth=True,
            depth_source="ultrasonic_echo"
        )
        self.landmarks[lm_id] = lm
        self.last_updated_at = time.time()
        return lm
    
    def update_object_track(self, track_id: int, class_name: str, class_id: int,
                             box_normalized: Dict, confidence: float,
                             frame_id: int, timestamp_ms: int,
                             acoustic_dist_m: Optional[float] = None) -> ObjectTrack:
        """Update an object track from YOLO detection. Creates track if new."""
        if track_id in self.object_tracks:
            track = self.object_tracks[track_id]
            track.last_frame = frame_id
            track.observation_count += 1
            track.last_box_normalized = box_normalized
            track.last_confidence = confidence
            track.is_active = True
        else:
            track = ObjectTrack(
                track_id=track_id,
                class_name=class_name,
                class_id=class_id,
                first_frame=frame_id,
                last_frame=frame_id,
                observation_count=1,
                last_box_normalized=box_normalized,
                last_confidence=confidence,
            )
            self.object_tracks[track_id] = track
        
        # Only create/update 3D landmark if we have a documented depth source
        if acoustic_dist_m is not None and acoustic_dist_m > 0:
            cx = box_normalized.get("x", 0.5) + box_normalized.get("w", 0) / 2.0
            cy = box_normalized.get("y", 0.5) + box_normalized.get("h", 0) / 2.0
            scene_x = (cx - 0.5) * 2.0 * acoustic_dist_m * 0.6
            scene_y = -(cy - 0.5) * 1.5 * acoustic_dist_m * 0.45
            scene_z = -acoustic_dist_m
            
            track.has_3d_position = True
            track.position_3d = [round(scene_x, 3), round(scene_y, 3), round(scene_z, 3)]
            track.depth_source = "ultrasonic_acoustic_correlation"
            
            lm_id = f"track-{track_id}"
            if lm_id in self.landmarks:
                lm = self.landmarks[lm_id]
                lm.x, lm.y, lm.z = scene_x, scene_y, scene_z
                lm.observation_count += 1
                lm.last_observed_frame = frame_id
                lm.last_observed_ms = timestamp_ms
                lm.label = class_name
                lm.confidence = confidence
                lm.is_stale = False
            else:
                lm = Landmark(
                    id=lm_id, x=scene_x, y=scene_y, z=scene_z,
                    label=class_name, confidence=confidence,
                    observation_count=1,
                    first_observed_frame=frame_id, last_observed_frame=frame_id,
                    first_observed_ms=timestamp_ms, last_observed_ms=timestamp_ms,
                    uncertainty=0.25,
                    provenance="estimated",
                    source="vision_track",
                    track_id=track_id,
                    has_valid_depth=True,
                    depth_source="ultrasonic_acoustic_correlation"
                )
                self.landmarks[lm_id] = lm
            track.landmark_id = lm_id
        else:
            track.has_3d_position = False
            track.position_3d = None
            track.depth_source = None
        
        self.last_updated_at = time.time()
        return track
    
    def mark_stale_entries(self, current_frame_id: int):
        """Mark landmarks and tracks that haven't been observed recently."""
        self.current_frame_id = current_frame_id
        for lm in self.landmarks.values():
            if not lm.is_stale and (current_frame_id - lm.last_observed_frame) > STALE_FRAME_THRESHOLD:
                lm.is_stale = True
        for track in self.object_tracks.values():
            if track.is_active and (current_frame_id - track.last_frame) > STALE_FRAME_THRESHOLD:
                track.is_active = False
    
    def add_camera_pose(self, frame_id: int, timestamp_ms: int,
                         position: Optional[List[float]] = None,
                         rotation_quat: Optional[List[float]] = None,
                         tracking_state: str = "tracking",
                         source: str = "dead_reckoning"):
        """Record a camera pose in the trajectory."""
        pose = {
            "frame_id": frame_id,
            "timestamp_ms": timestamp_ms,
            "position": position,
            "rotation_quat": rotation_quat,
            "tracking_state": tracking_state,
            "source": source,
        }
        self.camera_poses.append(pose)
        if len(self.camera_poses) > 5000:
            self.camera_poses = self.camera_poses[-4000:]
        self.last_updated_at = time.time()
    
    def reset(self):
        """Explicit map reset. Clears all landmarks, tracks, and poses."""
        self.landmarks.clear()
        self.object_tracks.clear()
        self.camera_poses.clear()
        self.current_frame_id = 0
        self.current_timestamp_ms = 0
        self._landmark_counter = 0
        self.last_updated_at = time.time()
        logger.info(f"Map state reset for session {self.session_id}")
    
    def get_active_landmarks(self) -> List[Landmark]:
        return [lm for lm in self.landmarks.values() if not lm.is_stale]
    
    def get_all_landmarks_serializable(self) -> List[Dict]:
        return [
            {
                "id": lm.id, "x": round(lm.x, 4), "y": round(lm.y, 4), "z": round(lm.z, 4),
                "label": lm.label, "confidence": lm.confidence,
                "observation_count": lm.observation_count,
                "first_observed_frame": lm.first_observed_frame,
                "last_observed_frame": lm.last_observed_frame,
                "uncertainty": round(lm.uncertainty, 4),
                "provenance": lm.provenance, "source": lm.source,
                "track_id": lm.track_id, "is_stale": lm.is_stale,
                "has_valid_depth": lm.has_valid_depth,
                "depth_source": lm.depth_source,
            }
            for lm in self.landmarks.values()
        ]
    
    def get_active_tracks_serializable(self) -> List[Dict]:
        return [
            {
                "track_id": t.track_id, "class_name": t.class_name,
                "observation_count": t.observation_count,
                "last_box_normalized": t.last_box_normalized,
                "last_confidence": t.last_confidence,
                "has_3d_position": t.has_3d_position,
                "position_3d": t.position_3d,
                "depth_source": t.depth_source,
                "landmark_id": t.landmark_id,
                "is_active": t.is_active,
            }
            for t in self.object_tracks.values() if t.is_active
        ]
    
    def _find_nearest_landmark(self, x: float, y: float, z: float,
                                source: Optional[str] = None,
                                max_distance: float = 0.3) -> Optional[Landmark]:
        best = None
        best_dist = max_distance
        for lm in self.landmarks.values():
            if source and lm.source != source:
                continue
            if lm.is_stale:
                continue
            d = math.sqrt((lm.x - x)**2 + (lm.y - y)**2 + (lm.z - z)**2)
            if d < best_dist:
                best = lm
                best_dist = d
        return best
    
    def get_trajectory_serializable(self) -> List[Dict]:
        return self.camera_poses[-300:]

    def export_map(self) -> Dict:
        return {
            "format": "esm-map-v1",
            "session_id": self.session_id,
            "landmarks": self.get_all_landmarks_serializable(),
            "object_tracks": self.get_active_tracks_serializable(),
            "camera_poses": self.camera_poses[-500:],
            "coordinate_transform": {
                "slam_to_scene": self.coordinate_transform.slam_to_scene,
                "scale": self.coordinate_transform.scale,
                "source": self.coordinate_transform.source,
            },
            "calibration": {
                "camera_fov_h_deg": self.calibration.camera_fov_h_deg,
                "ultrasonic_beam_deg": self.calibration.ultrasonic_beam_deg,
            },
            "status": self.get_status(),
        }
