from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

class Vec3(BaseModel):
    x: float
    y: float
    z: float

class SensorSampleBase(BaseModel):
    v: Literal[1] = 1
    type: Literal["sample"] = "sample"
    ts_ms: int
    distance_cm: Optional[float] = None
    echo_valid: bool
    accel_m_s2: Optional[Vec3] = None
    gyro_rad_s: Optional[Vec3] = None

class SensorSampleCreate(SensorSampleBase):
    session_id: str

class SensorSampleResponse(SensorSampleBase):
    id: int
    session_id: str
    received_at: datetime

    class Config:
        from_attributes = True

class SpatialPointBase(BaseModel):
    id: str
    ts_ms: int
    x: float
    y: float
    z: float
    distance: float
    intensity: float = 1.0
    uncertainty: float = 0.05
    quality_flag: str = "measured"

class SpatialPointCreate(SpatialPointBase):
    session_id: str

class SpatialPointResponse(SpatialPointBase):
    session_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class BoundingBox(BaseModel):
    x: float
    y: float
    w: float
    h: float

class VisionDetectionBase(BaseModel):
    id: str
    timestamp: int
    label: str
    confidence: float
    box: BoundingBox
    est_distance_m: Optional[float] = None
    spatial_coords: Optional[Vec3] = None
    is_approximate: bool = True

class VisionDetectionCreate(VisionDetectionBase):
    session_id: str

class VisionDetectionResponse(VisionDetectionBase):
    session_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class SessionCreate(BaseModel):
    name: str = Field(default="Untitled scan", max_length=255)
    source_mode: Literal["hardware", "demo"] = "hardware"
    notes: Optional[str] = None
    calibration_config: Optional[Dict[str, Any]] = None

class SessionResponse(BaseModel):
    id: str
    name: str
    source_mode: str
    status: str
    created_at: datetime
    finalized_at: Optional[datetime] = None
    sample_count: int
    point_count: int
    notes: Optional[str] = None
    calibration_config: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class SessionDetailResponse(SessionResponse):
    samples: List[SensorSampleResponse] = []
    points: List[SpatialPointResponse] = []
    detections: List[VisionDetectionResponse] = []

# WebSocket Event Schemas
class WSEvent(BaseModel):
    event: str
    timestamp: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp() * 1000))
    session_id: Optional[str] = None
    payload: Dict[str, Any]


# --- Part 2: Real-time Vision, Tracking & Path Awareness Schemas ---

class NormalizedBoundingBox(BaseModel):
    # Normalized coordinates in [0, 1] relative to image dimensions
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    w: float = Field(..., ge=0.0, le=1.0)
    h: float = Field(..., ge=0.0, le=1.0)

class PixelBoundingBox(BaseModel):
    xmin: int
    ymin: int
    xmax: int
    ymax: int

class VisionDetectionExtended(BaseModel):
    id: str
    session_id: Optional[str] = None
    frame_id: int
    timestamp_ms: int
    class_name: str
    class_id: int
    confidence: float = Field(..., ge=0.0, le=1.0)
    box_normalized: NormalizedBoundingBox
    box_pixel: Optional[PixelBoundingBox] = None
    track_id: Optional[int] = None
    # Path & corridor awareness flags
    overlaps_path_corridor: bool = False
    corridor_overlap_ratio: float = 0.0
    is_path_obstruction: bool = False
    # Geometric and uncertainty flags
    is_approximate: bool = True
    uncertainty: float = Field(default=0.15, description="Model uncertainty metric")
    latency_ms: Optional[float] = None
    acoustic_candidate_dist_m: Optional[float] = None
    provenance: Literal["measured", "estimated", "illustrative"] = "estimated"

class VisionStatusEvent(BaseModel):
    model_name: str
    model_ready: bool
    device: str
    input_size: int
    confidence_threshold: float
    iou_threshold: float
    tracking_enabled: bool
    processed_fps: float = 0.0
    avg_latency_ms: float = 0.0

class PathCorridorConfig(BaseModel):
    # Central visual corridor in normalized camera coordinates
    x_min: float = Field(default=0.30, ge=0.0, le=1.0)
    x_max: float = Field(default=0.70, ge=0.0, le=1.0)
    y_min: float = Field(default=0.35, ge=0.0, le=1.0)
    y_max: float = Field(default=1.00, ge=0.0, le=1.0)


# --- Part 3: Persistent Map & SLAM Schemas ---

class LandmarkSchema(BaseModel):
    id: str
    x: float
    y: float
    z: float
    label: Optional[str] = None
    confidence: float = 0.5
    observation_count: int = 1
    first_observed_frame: int = 0
    last_observed_frame: int = 0
    uncertainty: float = 0.15
    provenance: Literal["measured", "estimated", "illustrative"] = "estimated"
    source: str = "unknown"
    track_id: Optional[int] = None
    is_stale: bool = False
    has_valid_depth: bool = False
    depth_source: Optional[str] = None

class ObjectTrackSchema(BaseModel):
    track_id: int
    class_name: str
    observation_count: int = 0
    last_box_normalized: Optional[Dict[str, float]] = None
    last_confidence: float = 0.0
    has_3d_position: bool = False
    position_3d: Optional[List[float]] = None
    depth_source: Optional[str] = None
    landmark_id: Optional[str] = None
    is_active: bool = True

class CameraPoseSchema(BaseModel):
    frame_id: int
    timestamp_ms: int
    position: Optional[List[float]] = None
    rotation_quat: Optional[List[float]] = None
    tracking_state: str = "tracking"
    source: str = "dead_reckoning"

class SLAMStatusSchema(BaseModel):
    state: str = "unavailable"
    engine_name: str = "none"
    engine_version: Optional[str] = None
    num_map_points: int = 0
    num_keyframes: int = 0
    tracking_fps: float = 0.0
    scale_available: bool = False
    scale_source: Optional[str] = None
    last_error: Optional[str] = None

class MapStatusSchema(BaseModel):
    session_id: str = "global"
    total_landmarks: int = 0
    active_landmarks: int = 0
    stale_landmarks: int = 0
    total_object_tracks: int = 0
    active_object_tracks: int = 0
    camera_pose_count: int = 0
    current_frame_id: int = 0
    coordinate_transform_source: str = "identity"
    slam_status: Optional[SLAMStatusSchema] = None

class MapUpdateEvent(BaseModel):
    """Sent from backend to frontend when map state changes."""
    landmarks: List[LandmarkSchema] = []
    active_tracks: List[ObjectTrackSchema] = []
    camera_poses: List[CameraPoseSchema] = []
    map_status: MapStatusSchema = MapStatusSchema()

class MapExportSchema(BaseModel):
    format: str = "esm-map-v1"
    session_id: str
    landmarks: List[LandmarkSchema] = []
    object_tracks: List[ObjectTrackSchema] = []
    camera_poses: List[CameraPoseSchema] = []
    coordinate_transform: Dict[str, Any] = {}
    calibration: Dict[str, Any] = {}
    status: Dict[str, Any] = {}

