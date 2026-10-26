import asyncio
import json
import struct
import pytest
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient
from app.main import app
from app.database.session import init_db

@pytest.fixture(autouse=True)
def prepare_db():
    asyncio.run(init_db())


def test_websocket_ping_pong():
    client = TestClient(app)
    with client.websocket_connect("/ws/test-session-1") as websocket:
        # Initial vision status event
        initial_msg = websocket.receive_json()
        assert initial_msg["event"] == "vision.status"
        assert initial_msg["payload"]["model_ready"] is True

        # Initial SLAM status event
        slam_msg = websocket.receive_json()
        assert slam_msg["event"] == "slam.status"
        assert "state" in slam_msg["payload"]

        # Send ping
        websocket.send_json({"event": "ping", "timestamp": 123456789})
        response = websocket.receive_json()
        assert response["event"] == "pong"
        assert response["timestamp"] == 123456789


def test_websocket_sensor_sample_forward_and_projection():
    client = TestClient(app)
    with client.websocket_connect("/ws/test-session-2") as websocket:
        # Read initial vision status & slam status
        _ = websocket.receive_json()
        _ = websocket.receive_json()

        # Send sensor sample
        sample_payload = {
            "v": 1,
            "type": "sample",
            "ts_ms": 1000,
            "distance_cm": 120.0,
            "echo_valid": True,
            "accel_m_s2": {"x": 0.0, "y": 9.8, "z": 0.0},
            "gyro_rad_s": {"x": 0.0, "y": 0.0, "z": 0.0}
        }
        websocket.send_json({
            "event": "sensor.sample",
            "session_id": "test-session-2",
            "payload": sample_payload
        })

        # Expect broadcast of sensor.sample
        msg1 = websocket.receive_json()
        assert msg1["event"] == "sensor.sample"
        assert msg1["payload"]["distance_cm"] == 120.0

        # Expect broadcast of derived spatial.point
        msg2 = websocket.receive_json()
        assert msg2["event"] == "spatial.point"
        assert msg2["payload"]["distance"] == pytest.approx(1.2, 0.01)
        assert msg2["payload"]["quality_flag"] == "measured"


def test_websocket_binary_frame_transport():
    import numpy as np
    import cv2

    client = TestClient(app)
    with client.websocket_connect("/ws/test-session-3") as websocket:
        # Consume initial vision status & slam status
        _ = websocket.receive_json()
        _ = websocket.receive_json()

        # Generate a small 160x120 dummy JPEG
        dummy_img = np.zeros((120, 160, 3), dtype=np.uint8)
        _, jpeg_buf = cv2.imencode(".jpg", dummy_img)
        jpeg_bytes = jpeg_buf.tobytes()

        # Binary packet: 8 bytes header (uint32 frame_id=42, uint32 ts_ms=2500) + jpeg bytes
        header = struct.pack("<II", 42, 2500)
        packet = header + jpeg_bytes

        websocket.send_bytes(packet)

        # Receive vision.detection broadcast
        resp = websocket.receive_json()
        assert resp["event"] == "vision.detection"
        assert resp["payload"]["frame_id"] == 42
        assert "detections" in resp["payload"]
        assert resp["payload"]["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_session_replay_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create a session
        create_res = await ac.post("/api/v1/sessions", json={
            "name": "Replay Validation Run",
            "source_mode": "hardware"
        })
        assert create_res.status_code == 201
        sess_id = create_res.json()["id"]

        # 2. Add sequential samples
        for i, dist in enumerate([100.0, 95.0, 90.0]):
            res = await ac.post(f"/api/v1/sessions/{sess_id}/samples", json={
                "v": 1,
                "type": "sample",
                "ts_ms": 1000 + i * 250,
                "distance_cm": dist,
                "echo_valid": True,
                "accel_m_s2": {"x": 0.0, "y": 9.8, "z": 0.0},
                "gyro_rad_s": {"x": 0.0, "y": 0.0, "z": 0.0}
            })
            assert res.status_code == 200

        # 3. Retrieve Replay Stream
        replay_res = await ac.get(f"/api/v1/sessions/{sess_id}/replay")
        assert replay_res.status_code == 200
        replay_data = replay_res.json()

        assert replay_data["session"]["id"] == sess_id
        assert replay_data["event_count"] >= 3
        events = replay_data["events"]

        # Verify time-ordered monotonicity
        timestamps = [ev["timestamp_ms"] for ev in events]
        assert timestamps == sorted(timestamps)
