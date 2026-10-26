import pytest
import math
from app.mapping.map_state import PersistentMapState, Landmark, STALE_FRAME_THRESHOLD
from app.mapping.slam_interface import UnavailableSLAMBackend, SLAMState

class TestPersistentMapState:
    def test_add_ultrasonic_landmark(self):
        m = PersistentMapState("test-session")
        lm = m.add_ultrasonic_landmark(
            point_id="1000-0", x=0.0, y=0.0, z=-1.0,
            distance_m=1.0, uncertainty=0.05,
            frame_id=1, timestamp_ms=1000
        )
        assert lm.provenance == "measured"
        assert lm.source == "ultrasonic"
        assert lm.has_valid_depth is True
        assert lm.depth_source == "ultrasonic_echo"
        assert len(m.landmarks) == 1

    def test_landmark_merge_nearby(self):
        m = PersistentMapState("test-session")
        lm1 = m.add_ultrasonic_landmark("p1", 0.0, 0.0, -1.0, 1.0, 0.05, 1, 1000)
        lm2 = m.add_ultrasonic_landmark("p2", 0.05, 0.0, -1.05, 1.05, 0.05, 2, 1250)
        assert len(m.landmarks) == 1
        assert lm2.observation_count == 2

    def test_landmark_no_merge_far(self):
        m = PersistentMapState("test-session")
        m.add_ultrasonic_landmark("p1", 0.0, 0.0, -1.0, 1.0, 0.05, 1, 1000)
        m.add_ultrasonic_landmark("p2", 2.0, 0.0, -3.0, 3.5, 0.05, 2, 1250)
        assert len(m.landmarks) == 2

    def test_object_track_without_depth(self):
        m = PersistentMapState("test-session")
        track = m.update_object_track(
            track_id=1, class_name="chair", class_id=56,
            box_normalized={"x": 0.3, "y": 0.4, "w": 0.2, "h": 0.3},
            confidence=0.85, frame_id=1, timestamp_ms=1000,
            acoustic_dist_m=None
        )
        assert track.has_3d_position is False
        assert track.position_3d is None
        assert track.landmark_id is None
        assert "track-1" not in m.landmarks

    def test_object_track_with_depth(self):
        m = PersistentMapState("test-session")
        track = m.update_object_track(
            track_id=2, class_name="person", class_id=0,
            box_normalized={"x": 0.35, "y": 0.3, "w": 0.3, "h": 0.4},
            confidence=0.91, frame_id=1, timestamp_ms=1000,
            acoustic_dist_m=1.5
        )
        assert track.has_3d_position is True
        assert track.position_3d is not None
        assert track.depth_source == "ultrasonic_acoustic_correlation"
        assert "track-2" in m.landmarks
        lm = m.landmarks["track-2"]
        assert lm.has_valid_depth is True
        assert lm.provenance == "estimated"

    def test_mark_stale_entries(self):
        m = PersistentMapState("test-session")
        m.add_ultrasonic_landmark("p1", 0.0, 0.0, -1.0, 1.0, 0.05, 1, 1000)
        assert m.landmarks["us-p1"].is_stale is False
        m.mark_stale_entries(STALE_FRAME_THRESHOLD + 5)
        assert m.landmarks["us-p1"].is_stale is True

    def test_map_reset(self):
        m = PersistentMapState("test-session")
        m.add_ultrasonic_landmark("p1", 0.0, 0.0, -1.0, 1.0, 0.05, 1, 1000)
        m.update_object_track(1, "chair", 56, {"x": 0.3, "y": 0.4, "w": 0.2, "h": 0.3}, 0.85, 1, 1000)
        assert len(m.landmarks) >= 1
        assert len(m.object_tracks) == 1
        m.reset()
        assert len(m.landmarks) == 0
        assert len(m.object_tracks) == 0
        assert len(m.camera_poses) == 0

    def test_export_map(self):
        m = PersistentMapState("test-session")
        m.add_ultrasonic_landmark("p1", 0.0, 0.0, -1.0, 1.0, 0.05, 1, 1000)
        export = m.export_map()
        assert export["format"] == "esm-map-v1"
        assert export["session_id"] == "test-session"
        assert len(export["landmarks"]) == 1
        assert export["landmarks"][0]["provenance"] == "measured"

    def test_coordinate_transform_default_identity(self):
        m = PersistentMapState("test-session")
        assert m.coordinate_transform.source == "identity"
        assert m.coordinate_transform.scale == 1.0

    def test_camera_pose_trajectory(self):
        m = PersistentMapState("test-session")
        m.add_camera_pose(1, 1000, position=[0.0, 0.0, 0.0], source="dead_reckoning")
        m.add_camera_pose(2, 1250, position=[0.1, 0.0, -0.2], source="dead_reckoning")
        assert len(m.camera_poses) == 2
        assert m.camera_poses[1]["position"] == [0.1, 0.0, -0.2]


class TestSLAMInterface:
    def test_unavailable_backend_reports_honestly(self):
        backend = UnavailableSLAMBackend()
        assert backend.is_available() is False
        assert backend.get_name() == "none"
        status = backend.get_status()
        assert status.state == SLAMState.UNAVAILABLE
        assert status.num_map_points == 0
        assert "No SLAM engine installed" in status.last_error

    def test_unavailable_backend_process_frame_returns_none(self):
        backend = UnavailableSLAMBackend()
        result = backend.process_frame(b"fake", 1, 1000)
        assert result is None

    def test_unavailable_backend_empty_map(self):
        backend = UnavailableSLAMBackend()
        assert backend.get_map_points() == []
        assert backend.get_trajectory() == []

    def test_unavailable_backend_initialize_fails(self):
        backend = UnavailableSLAMBackend()
        assert backend.initialize({}) is False

    def test_unavailable_backend_safe_operations(self):
        backend = UnavailableSLAMBackend()
        backend.reset()
        backend.shutdown()
        backend.set_scale(1.0, "test")
