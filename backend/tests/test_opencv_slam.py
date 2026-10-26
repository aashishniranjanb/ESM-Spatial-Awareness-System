"""
Unit tests for OpenCV Visual Odometry / SLAM backend.
"""
import pytest
import numpy as np
import cv2
from app.mapping.opencv_slam import OpenCVVisualSLAMBackend
from app.mapping.slam_interface import SLAMState


def test_opencv_slam_init():
    slam = OpenCVVisualSLAMBackend(focal_length=500.0, cx=320.0, cy=240.0)
    assert slam.is_available() is True
    assert slam.get_name() == "opencv-vo-slam"
    status = slam.get_status()
    assert status.state == SLAMState.NOT_INITIALIZED
    
    assert slam.initialize() is True
    assert slam.get_status().state == SLAMState.INITIALIZING


def test_opencv_slam_tracking_and_scale():
    slam = OpenCVVisualSLAMBackend(focal_length=500.0, cx=320.0, cy=240.0)
    slam.initialize()

    # Ground scale with simulated ultrasonic distance 1.5m
    slam.set_scale(1.5, source="ultrasonic")
    status = slam.get_status()
    assert status.scale_available is True
    assert status.scale_source == "ultrasonic"

    # Frame 1: Rich feature scene
    np.random.seed(42)
    img1 = np.zeros((480, 640), dtype=np.uint8)
    for _ in range(80):
        x = int(np.random.randint(40, 600))
        y = int(np.random.randint(40, 440))
        cv2.circle(img1, (x, y), 5, 255, -1)

    _, buf1 = cv2.imencode(".jpg", img1)
    pose1 = slam.process_frame(buf1.tobytes(), frame_id=1, timestamp_ms=1000)
    # First frame initializes keyframe and feature detection
    assert pose1 is None
    assert slam.num_keyframes >= 1

    # Frame 2: Shifted slightly (simulating camera forward/lateral motion)
    M = np.float32([[1, 0, 4], [0, 1, 2]])
    img2 = cv2.warpAffine(img1, M, (640, 480))
    _, buf2 = cv2.imencode(".jpg", img2)
    pose2 = slam.process_frame(buf2.tobytes(), frame_id=2, timestamp_ms=1060)

    assert pose2 is not None
    assert pose2.position is not None
    assert len(pose2.position) == 3
    assert slam.get_status().state == SLAMState.TRACKING
    assert len(slam.get_trajectory()) == 1


def test_opencv_slam_reset():
    slam = OpenCVVisualSLAMBackend()
    slam.initialize()
    slam.reset()
    assert slam.get_status().state == SLAMState.NOT_INITIALIZED
    assert len(slam.get_trajectory()) == 0
    assert len(slam.get_map_points()) == 0
