import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.session import init_db

@pytest.fixture(autouse=True)
async def prepare_db():
    await init_db()


@pytest.mark.asyncio
async def test_health_and_readiness():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

        res_ready = await ac.get("/ready")
        assert res_ready.status_code == 200
        assert res_ready.json()["status"] == "ready"

@pytest.mark.asyncio
async def test_session_lifecycle_and_persistence():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create Session
        create_res = await ac.post("/api/v1/sessions", json={
            "name": "Laboratory Corridor Test",
            "source_mode": "hardware"
        })
        assert create_res.status_code == 201
        session_data = create_res.json()
        session_id = session_data["id"]
        assert session_data["name"] == "Laboratory Corridor Test"

        # 2. Ingest Sample
        sample_res = await ac.post(f"/api/v1/sessions/{session_id}/samples", json={
            "v": 1,
            "type": "sample",
            "ts_ms": 123456,
            "distance_cm": 85.5,
            "echo_valid": True,
            "accel_m_s2": {"x": 0.0, "y": 9.8, "z": 0.0},
            "gyro_rad_s": {"x": 0.0, "y": 0.0, "z": 0.0}
        })
        assert sample_res.status_code == 200

        # 3. Verify Points Persisted
        points_res = await ac.get(f"/api/v1/sessions/{session_id}/points")
        assert points_res.status_code == 200
        points = points_res.json()
        assert len(points) == 1
        assert points[0]["distance"] == pytest.approx(0.855, 0.01)

        # 4. Export JSON
        export_res = await ac.get(f"/api/v1/sessions/{session_id}/export/json")
        assert export_res.status_code == 200
        export_data = export_res.json()
        assert export_data["format"] == "echomap-scan-v2"
        assert len(export_data["points"]) == 1
