"""
Replaceable SLAM backend interface for ESM.

Evaluated engines:
- ORB-SLAM3: GPLv3, requires native C++ build (OpenCV, Eigen3, Pangolin, DBoW2, g2o).
  No pip-installable Python bindings for Windows. Requires Docker/WSL2 or manual MSVC compilation.
- Stella-VSLAM: BSD-2, fork of OpenVSLAM. Same native dependency issue.
- pySLAM: Python framework, but still requires C++ optimization helpers.

Current status: No SLAM engine is installed. The interface is ready for integration
when a compatible engine becomes available.
"""
import abc
import enum
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

class SLAMState(enum.Enum):
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    TRACKING = "tracking"
    TRACKING_LOST = "tracking_lost"
    RELOCALIZATION = "relocalization"
    UNAVAILABLE = "unavailable"

@dataclass
class CameraPose:
    """6-DOF camera pose in the SLAM coordinate frame."""
    timestamp_ms: int
    frame_id: int
    transform_4x4: Optional[List[float]] = None
    position: Optional[List[float]] = None  # [x, y, z]
    rotation_quat: Optional[List[float]] = None  # [qx, qy, qz, qw]
    tracking_state: SLAMState = SLAMState.NOT_INITIALIZED
    scale_factor: Optional[float] = None
    scale_source: Optional[str] = None  # "ultrasonic", "known_object", "imu", None

@dataclass
class MapPoint3D:
    """A 3D map point observed by the SLAM engine."""
    id: str
    position: List[float]  # [x, y, z] in SLAM frame
    num_observations: int = 1
    last_observed_frame: int = 0
    uncertainty: float = 0.1
    provenance: str = "estimated"  # never "measured" unless grounded by rangefinder

@dataclass
class SLAMStatus:
    state: SLAMState
    engine_name: str
    engine_version: Optional[str] = None
    num_map_points: int = 0
    num_keyframes: int = 0
    tracking_fps: float = 0.0
    scale_available: bool = False
    scale_source: Optional[str] = None
    last_error: Optional[str] = None
    initialized_at: Optional[float] = None

class SLAMBackend(abc.ABC):
    """Abstract interface for a visual SLAM engine."""
    
    @abc.abstractmethod
    def get_name(self) -> str: ...
    
    @abc.abstractmethod
    def get_status(self) -> SLAMStatus: ...
    
    @abc.abstractmethod
    def is_available(self) -> bool: ...
    
    @abc.abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the SLAM engine. Returns True on success."""
        ...
    
    @abc.abstractmethod
    def process_frame(self, image_bytes: bytes, frame_id: int, timestamp_ms: int) -> Optional[CameraPose]:
        """Process a single frame. Returns camera pose if tracking, None if lost."""
        ...
    
    @abc.abstractmethod
    def get_map_points(self) -> List[MapPoint3D]:
        """Return current map points."""
        ...
    
    @abc.abstractmethod
    def get_trajectory(self) -> List[CameraPose]:
        """Return estimated camera trajectory."""
        ...
    
    @abc.abstractmethod
    def reset(self) -> None:
        """Reset the SLAM engine, clearing map and trajectory."""
        ...
    
    @abc.abstractmethod
    def shutdown(self) -> None:
        """Clean up resources."""
        ...
    
    @abc.abstractmethod
    def set_scale(self, scale_factor: float, source: str) -> None:
        """Set metric scale from an external source (e.g., ultrasonic rangefinder)."""
        ...


class UnavailableSLAMBackend(SLAMBackend):
    """
    Explicit unavailable SLAM backend.
    Reports honestly that no SLAM engine is installed.
    Does NOT fake tracking, map points, or camera poses.
    """
    
    def get_name(self) -> str:
        return "none"
    
    def get_status(self) -> SLAMStatus:
        return SLAMStatus(
            state=SLAMState.UNAVAILABLE,
            engine_name="none",
            engine_version=None,
            num_map_points=0,
            num_keyframes=0,
            tracking_fps=0.0,
            scale_available=False,
            scale_source=None,
            last_error="No SLAM engine installed. Install ORB-SLAM3 or compatible engine to enable visual mapping.",
        )
    
    def is_available(self) -> bool:
        return False
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        return False
    
    def process_frame(self, image_bytes: bytes, frame_id: int, timestamp_ms: int) -> Optional[CameraPose]:
        return None
    
    def get_map_points(self) -> List[MapPoint3D]:
        return []
    
    def get_trajectory(self) -> List[CameraPose]:
        return []
    
    def reset(self) -> None:
        pass
    
    def shutdown(self) -> None:
        pass
    
    def set_scale(self, scale_factor: float, source: str) -> None:
        pass
