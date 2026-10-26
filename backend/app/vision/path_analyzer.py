import logging
import time
from typing import List, Tuple
from app.schemas.schemas import VisionDetectionExtended, PathCorridorConfig, NormalizedBoundingBox

logger = logging.getLogger("esm.vision.path")

class PathAwarenessAnalyzer:
    """
    Computes visual corridor overlap and flags potential obstructions in camera-space.
    Crucial Rule: This represents an image-space visual aid. It does NOT assert ground-truth
    collision or certified route traversability.
    """
    def __init__(self, config: PathCorridorConfig = PathCorridorConfig()):
        self.config = config

    def update_config(self, config: PathCorridorConfig):
        self.config = config

    def calculate_overlap_ratio(self, box: NormalizedBoundingBox) -> float:
        """
        Calculates the 2D intersection-over-box-area between a detection box
        and the visual forward path corridor.
        """
        # Box bounds
        b_x1 = box.x
        b_y1 = box.y
        b_x2 = box.x + box.w
        b_y2 = box.y + box.h

        # Corridor bounds
        c_x1 = self.config.x_min
        c_y1 = self.config.y_min
        c_x2 = self.config.x_max
        c_y2 = self.config.y_max

        # Intersection bounds
        ix1 = max(b_x1, c_x1)
        iy1 = max(b_y1, c_y1)
        ix2 = min(b_x2, c_x2)
        iy2 = min(b_y2, c_y2)

        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0

        intersection_area = (ix2 - ix1) * (iy2 - iy1)
        box_area = max(1e-6, box.w * box.h)

        return min(1.0, intersection_area / box_area)

    def analyze_detections(self, detections: List[VisionDetectionExtended]) -> List[VisionDetectionExtended]:
        """
        Augments each detection with corridor overlap status and potential obstruction flags.
        """
        # Classes typically considered physical obstacles in standard COCO
        obstacle_classes = {
            "person", "chair", "couch", "table", "dining table", "bed", 
            "bicycle", "car", "motorcycle", "bus", "truck", "backpack", 
            "suitcase", "dog", "cat", "bench", "fire hydrant", "stop sign"
        }

        updated = []
        for det in detections:
            overlap = self.calculate_overlap_ratio(det.box_normalized)
            overlaps = overlap > 0.15 # At least 15% intersection with forward corridor
            
            # Obstruction heuristic: overlaps corridor and belongs to obstacle-capable classes
            is_obstacle = overlaps and (det.class_name.lower() in obstacle_classes)

            det.corridor_overlap_ratio = round(overlap, 3)
            det.overlaps_path_corridor = overlaps
            det.is_path_obstruction = is_obstacle
            updated.append(det)

        return updated
