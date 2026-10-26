import math
from typing import List, Optional, Tuple
from app.schemas.schemas import VisionDetectionExtended, SensorSampleBase

class SensorVisionAssociationEngine:
    """
    Experimental Sensor-to-Vision Association Layer.
    Crucial Principle: A single HC-SR04 ultrasonic echo has a ~15-degree conical beam
    and cannot decisively associate itself with an individual 2D camera detection.
    Any association is strictly labelled HEURISTIC / UNCERTAIN.
    """
    def __init__(self, fov_horizontal_deg: float = 65.0, ultrasonic_beam_deg: float = 15.0):
        self.fov_horizontal_deg = fov_horizontal_deg
        self.ultrasonic_beam_deg = ultrasonic_beam_deg

    def evaluate_association(
        self,
        latest_sample: Optional[SensorSampleBase],
        detections: List[VisionDetectionExtended]
    ) -> List[VisionDetectionExtended]:
        """
        Calculates whether any detection falls near the forward acoustic cone of the ultrasonic sensor.
        If so, attaches an experimental estimated distance without overriding the raw measurement.
        """
        if not latest_sample or not latest_sample.echo_valid or latest_sample.distance_cm is None:
            return detections

        dist_m = round(latest_sample.distance_cm / 100.0, 3)

        # Center of camera image corresponds to 0 deg relative to optical axis
        # Normalized x in [0, 1]; center is 0.5
        beam_half_width_norm = (self.ultrasonic_beam_deg / 2.0) / self.fov_horizontal_deg

        center_min = 0.5 - beam_half_width_norm
        center_max = 0.5 + beam_half_width_norm

        for det in detections:
            box = det.box_normalized
            box_center_x = box.x + (box.w / 2.0)
            
            # If the detection box's center lies within the forward acoustic projection cone
            if center_min <= box_center_x <= center_max:
                # Mark as candidate for acoustic correlation
                det.uncertainty = round(det.uncertainty * 0.9, 3) # Slightly reduced uncertainty
                # Attach heuristic distance tag for research inspection
                # Note: Marked as approximate; never certified truth
                det.acoustic_candidate_dist_m = dist_m

        return detections
