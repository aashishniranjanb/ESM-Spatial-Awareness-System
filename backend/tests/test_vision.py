import pytest
import numpy as np
import cv2
from app.schemas.schemas import (
    VisionDetectionExtended,
    NormalizedBoundingBox,
    PathCorridorConfig,
    SensorSampleBase
)
from app.vision.path_analyzer import PathAwarenessAnalyzer
from app.vision.yolo_pipeline import YOLOTrackingPipeline
from app.vision.association import SensorVisionAssociationEngine

def test_path_corridor_overlap_calculation():
    analyzer = PathAwarenessAnalyzer(PathCorridorConfig(x_min=0.3, x_max=0.7, y_min=0.3, y_max=1.0))

    # 1. Box completely inside corridor
    box_inside = NormalizedBoundingBox(x=0.4, y=0.4, w=0.2, h=0.2)
    assert pytest.approx(analyzer.calculate_overlap_ratio(box_inside), 0.01) == 1.0

    # 2. Box completely outside corridor (left)
    box_outside = NormalizedBoundingBox(x=0.05, y=0.4, w=0.15, h=0.2)
    assert analyzer.calculate_overlap_ratio(box_outside) == 0.0

    # 3. Box partially overlapping
    box_partial = NormalizedBoundingBox(x=0.25, y=0.4, w=0.2, h=0.2) # x ranges from 0.25 to 0.45; overlaps [0.3, 0.45] -> w=0.15
    ratio = analyzer.calculate_overlap_ratio(box_partial)
    assert 0.65 < ratio < 0.85

def test_path_awareness_obstruction_flagging():
    analyzer = PathAwarenessAnalyzer()
    
    det_obstacle = VisionDetectionExtended(
        id="det-1",
        frame_id=1,
        timestamp_ms=1000,
        class_name="chair",
        class_id=56,
        confidence=0.88,
        box_normalized=NormalizedBoundingBox(x=0.4, y=0.5, w=0.2, h=0.3),
    )
    det_non_obstacle = VisionDetectionExtended(
        id="det-2",
        frame_id=1,
        timestamp_ms=1000,
        class_name="cell phone",
        class_id=67,
        confidence=0.75,
        box_normalized=NormalizedBoundingBox(x=0.4, y=0.5, w=0.1, h=0.1),
    )

    results = analyzer.analyze_detections([det_obstacle, det_non_obstacle])
    assert results[0].overlaps_path_corridor is True
    assert results[0].is_path_obstruction is True
    
    assert results[1].overlaps_path_corridor is True
    assert results[1].is_path_obstruction is False  # phone is not a physical path obstacle

def test_sensor_vision_association_heuristic():
    engine = SensorVisionAssociationEngine()
    sample = SensorSampleBase(
        v=1,
        type="sample",
        ts_ms=5000,
        distance_cm=140.0,
        echo_valid=True
    )
    
    # Detection in center of field of view (around x=0.5)
    det_center = VisionDetectionExtended(
        id="det-c",
        frame_id=1,
        timestamp_ms=5000,
        class_name="person",
        class_id=0,
        confidence=0.92,
        box_normalized=NormalizedBoundingBox(x=0.42, y=0.2, w=0.16, h=0.6),
    )
    
    # Detection far off to the side (x=0.85)
    det_side = VisionDetectionExtended(
        id="det-s",
        frame_id=1,
        timestamp_ms=5000,
        class_name="bottle",
        class_id=39,
        confidence=0.70,
        box_normalized=NormalizedBoundingBox(x=0.85, y=0.2, w=0.1, h=0.2),
    )

    associated = engine.evaluate_association(sample, [det_center, det_side])
    assert associated[0].acoustic_candidate_dist_m == 1.4
    assert associated[1].acoustic_candidate_dist_m is None

def test_yolo_pipeline_frame_decoding_and_resilience():
    pipeline = YOLOTrackingPipeline()
    # 1. Invalid empty bytes
    assert pipeline.decode_frame(b"") is None
    assert pipeline.decode_frame(b"too_short") is None

    # 2. Valid synthetic encoded JPEG image
    img = np.zeros((240, 320, 3), dtype=np.uint8)
    img[60:180, 80:240] = [180, 100, 50]
    success, encoded = cv2.imencode(".jpg", img)
    assert success is True

    decoded = pipeline.decode_frame(encoded.tobytes())
    assert decoded is not None
    assert decoded.shape == (240, 320, 3)

    # 3. Process frame through pipeline
    dets, latency = pipeline.process_frame(encoded.tobytes(), frame_id=101)
    assert isinstance(dets, list)
    assert latency > 0.0
