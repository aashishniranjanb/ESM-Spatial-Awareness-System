import io
import time
import logging
from typing import List, Optional, Tuple
import cv2
import numpy as np
from app.schemas.schemas import (
    VisionDetectionExtended,
    NormalizedBoundingBox,
    PixelBoundingBox,
    VisionStatusEvent,
    PathCorridorConfig
)
from app.vision.path_analyzer import PathAwarenessAnalyzer

logger = logging.getLogger("esm.vision.yolo")

class YOLOTrackingPipeline:
    """
    Modular Ultralytics YOLO Object Detection and Tracking Engine with CPU-bound thread execution,
    bounded frame latency protection, and path-corridor awareness.
    """
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        imgsz: int = 320,
        conf_thresh: float = 0.35,
        iou_thresh: float = 0.45,
        enable_tracking: bool = True,
        device: str = "cpu"
    ):
        self.model_path = model_path
        self.imgsz = imgsz
        self.conf_thresh = conf_thresh
        self.iou_thresh = iou_thresh
        self.enable_tracking = enable_tracking
        self.device = device
        
        self.model = None
        self._is_ready = False
        self.path_analyzer = PathAwarenessAnalyzer()
        
        # Telemetry metrics
        self.processed_frames = 0
        self.last_latency_ms = 0.0
        self.fps_rolling = 0.0
        self._last_fps_time = time.time()
        self._fps_counter = 0

        self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            logger.info(f"Loading Ultralytics YOLO model from {self.model_path} (Device: {self.device})...")
            self.model = YOLO(self.model_path)
            self._is_ready = True
            logger.info("YOLO model initialized successfully.")
        except Exception as e:
            logger.warning(f"Failed to load YOLO model: {e}. Pipeline running in fallback mode.")
            self._is_ready = False

    def is_ready(self) -> bool:
        return self._is_ready

    def get_status(self) -> VisionStatusEvent:
        return VisionStatusEvent(
            model_name=self.model_path,
            model_ready=self._is_ready,
            device=self.device,
            input_size=self.imgsz,
            confidence_threshold=self.conf_thresh,
            iou_threshold=self.iou_thresh,
            tracking_enabled=self.enable_tracking,
            processed_fps=round(self.fps_rolling, 1),
            avg_latency_ms=round(self.last_latency_ms, 1)
        )

    def decode_frame(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """
        Validates and decodes image bytes into a BGR OpenCV NumPy array.
        """
        if not image_bytes or len(image_bytes) < 64:
            return None
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            logger.warning(f"Failed to decode frame bytes: {e}")
            return None

    def process_frame(
        self,
        image_bytes: bytes,
        frame_id: int,
        session_id: Optional[str] = None
    ) -> Tuple[List[VisionDetectionExtended], float]:
        """
        Executes YOLO inference/tracking on a single image frame.
        Returns (detections, latency_ms).
        """
        start_time = time.perf_counter()
        
        img = self.decode_frame(image_bytes)
        if img is None:
            return [], 0.0

        orig_h, orig_w = img.shape[:2]
        
        if not self._is_ready or self.model is None:
            # Fallback when model is not available
            latency = (time.perf_counter() - start_time) * 1000.0
            return [], latency

        detections: List[VisionDetectionExtended] = []
        try:
            if self.enable_tracking:
                # Use ByteTrack or BoT-SORT built into Ultralytics
                results = self.model.track(
                    source=img,
                    imgsz=self.imgsz,
                    conf=self.conf_thresh,
                    iou=self.iou_thresh,
                    device=self.device,
                    persist=True,
                    verbose=False
                )
            else:
                results = self.model.predict(
                    source=img,
                    imgsz=self.imgsz,
                    conf=self.conf_thresh,
                    iou=self.iou_thresh,
                    device=self.device,
                    verbose=False
                )

            res = results[0]
            boxes = res.boxes
            if boxes is not None and len(boxes) > 0:
                xyxy = boxes.xyxy.cpu().numpy()
                confs = boxes.conf.cpu().numpy()
                classes = boxes.cls.cpu().numpy()
                track_ids = boxes.id.cpu().numpy() if boxes.id is not None else [None] * len(boxes)

                names = self.model.names if hasattr(self.model, "names") else {}

                for i in range(len(boxes)):
                    x1, y1, x2, y2 = xyxy[i]
                    conf = float(confs[i])
                    cls_id = int(classes[i])
                    track_id = int(track_ids[i]) if track_ids[i] is not None else None
                    cls_name = names.get(cls_id, str(cls_id))

                    # Normalize bounding box into [0, 1]
                    norm_x = max(0.0, min(1.0, float(x1 / orig_w)))
                    norm_y = max(0.0, min(1.0, float(y1 / orig_h)))
                    norm_w = max(0.0, min(1.0, float((x2 - x1) / orig_w)))
                    norm_h = max(0.0, min(1.0, float((y2 - y1) / orig_h)))

                    det = VisionDetectionExtended(
                        id=f"det-{frame_id}-{i}",
                        session_id=session_id,
                        frame_id=frame_id,
                        timestamp_ms=int(time.time() * 1000),
                        class_name=cls_name,
                        class_id=cls_id,
                        confidence=round(conf, 3),
                        box_normalized=NormalizedBoundingBox(
                            x=round(norm_x, 4),
                            y=round(norm_y, 4),
                            w=round(norm_w, 4),
                            h=round(norm_h, 4)
                        ),
                        box_pixel=PixelBoundingBox(
                            xmin=int(x1),
                            ymin=int(y1),
                            xmax=int(x2),
                            ymax=int(y2)
                        ),
                        track_id=track_id,
                        is_approximate=True,
                        uncertainty=round(float(1.0 - conf), 3),
                        provenance="estimated"
                    )
                    detections.append(det)

        except Exception as e:
            logger.error(f"Inference error on frame {frame_id}: {e}")

        latency = (time.perf_counter() - start_time) * 1000.0
        self.last_latency_ms = latency

        # Analyze path corridor overlap
        detections = self.path_analyzer.analyze_detections(detections)
        for d in detections:
            d.latency_ms = round(latency, 1)

        # Update FPS
        self._fps_counter += 1
        self.processed_frames += 1
        now = time.time()
        if now - self._last_fps_time >= 1.0:
            self.fps_rolling = self._fps_counter / (now - self._last_fps_time)
            self._fps_counter = 0
            self._last_fps_time = now

        return detections, latency
