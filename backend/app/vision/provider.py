import abc
import time
from typing import List, Optional
from app.schemas.schemas import VisionDetectionBase, BoundingBox, Vec3

class VisionProvider(abc.ABC):
    @abc.abstractmethod
    def is_available(self) -> bool:
        """Returns True if the vision model weights and dependencies are ready."""
        pass

    @abc.abstractmethod
    def detect(self, image_bytes: Optional[bytes] = None) -> List[VisionDetectionBase]:
        """Runs detection on frame image."""
        pass

class MockOrPlaceholderVisionProvider(VisionProvider):
    """
    Standard production-oriented vision provider interface.
    When a heavy model (e.g. YOLO/ONNX) is not explicitly configured or installed,
    it returns clean empty detections and accurately marks detection as unavailable.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self._available = False

    def is_available(self) -> bool:
        return self._available

    def detect(self, image_bytes: Optional[bytes] = None) -> List[VisionDetectionBase]:
        if not self._available or not image_bytes:
            return []
        return []

class SyntheticDemoVisionProvider(VisionProvider):
    """
    Explicitly labeled synthetic provider for deterministic demo scenarios.
    Only active in demo mode. Never used for hardware sessions.
    """
    def __init__(self):
        self._step = 0

    def is_available(self) -> bool:
        return True

    def detect(self, image_bytes: Optional[bytes] = None) -> List[VisionDetectionBase]:
        self._step += 1
        ts = int(time.time() * 1000)
        # Cycle through simulated obstacles (Person, Chair, Doorway)
        items = [
            VisionDetectionBase(
                id=f"demo-det-{self._step}",
                timestamp=ts,
                label="Person (Wearer / Obstacle)",
                confidence=0.91,
                box=BoundingBox(x=0.35, y=0.2, w=0.3, h=0.6),
                est_distance_m=1.2,
                spatial_coords=Vec3(x=0.1, y=0.0, z=-1.2),
                is_approximate=True
            ),
            VisionDetectionBase(
                id=f"demo-det-{self._step}",
                timestamp=ts,
                label="Office Chair",
                confidence=0.84,
                box=BoundingBox(x=0.15, y=0.45, w=0.25, h=0.4),
                est_distance_m=2.1,
                spatial_coords=Vec3(x=-0.5, y=-0.3, z=-2.1),
                is_approximate=True
            ),
            VisionDetectionBase(
                id=f"demo-det-{self._step}",
                timestamp=ts,
                label="Open Doorway",
                confidence=0.88,
                box=BoundingBox(x=0.4, y=0.1, w=0.35, h=0.8),
                est_distance_m=3.4,
                spatial_coords=Vec3(x=0.2, y=0.2, z=-3.4),
                is_approximate=True
            ),
        ]
        return [items[self._step % len(items)]]
