import pytest
import math
from app.spatial.pipeline import SpatialPipeline
from app.schemas.schemas import SensorSampleBase, Vec3

def test_spatial_pipeline_unit_conversion_and_projection():
    pipeline = SpatialPipeline()
    # Sample with 100 cm distance, valid echo, no tilt
    sample = SensorSampleBase(
        v=1,
        type="sample",
        ts_ms=1000,
        distance_cm=100.0,
        echo_valid=True,
        accel_m_s2=Vec3(x=0.0, y=9.8, z=0.0),
        gyro_rad_s=Vec3(x=0.0, y=0.0, z=0.0)
    )
    point, reason = pipeline.project_sample(sample)
    assert point is not None
    assert reason is None
    # 100 cm -> 1.0 metre
    assert pytest.approx(point.distance, 0.01) == 1.0
    # Forward is -Z in our Three.js coordinate system
    assert pytest.approx(point.z, 0.01) == -1.0
    assert pytest.approx(point.x, 0.01) == 0.0

def test_spatial_pipeline_rejection_of_invalid_echo():
    pipeline = SpatialPipeline()
    sample = SensorSampleBase(
        v=1,
        type="sample",
        ts_ms=1000,
        distance_cm=None,
        echo_valid=False,
    )
    point, reason = pipeline.project_sample(sample)
    assert point is None
    assert "No valid ultrasonic echo" in reason
    assert pipeline.rejected_count == 1

def test_spatial_pipeline_spike_filter():
    pipeline = SpatialPipeline()
    # Establish baseline at 100cm
    for i in range(5):
        pipeline.project_sample(SensorSampleBase(
            v=1, type="sample", ts_ms=1000 + i * 250, distance_cm=100.0, echo_valid=True
        ))
    
    # Sudden implausible spike to 350cm
    spike_sample = SensorSampleBase(
        v=1, type="sample", ts_ms=2500, distance_cm=350.0, echo_valid=True
    )
    point, reason = pipeline.project_sample(spike_sample)
    assert point is None
    assert "spike" in reason.lower()
