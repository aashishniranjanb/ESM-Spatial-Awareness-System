from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

def utcnow():
    return datetime.now(timezone.utc)

class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(32), default="hardware")  # 'hardware' or 'demo'
    status: Mapped[str] = mapped_column(String(32), default="created")  # 'created', 'started', 'paused', 'completed'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    point_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    calibration_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    samples: Mapped[List["SensorSampleModel"]] = relationship("SensorSampleModel", back_populates="session", cascade="all, delete-orphan")
    points: Mapped[List["SpatialPointModel"]] = relationship("SpatialPointModel", back_populates="session", cascade="all, delete-orphan")
    detections: Mapped[List["VisionDetectionModel"]] = relationship("VisionDetectionModel", back_populates="session", cascade="all, delete-orphan")


class SensorSampleModel(Base):
    __tablename__ = "sensor_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    ts_ms: Mapped[int] = mapped_column(Integer, index=True)
    distance_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    echo_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    accel_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accel_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accel_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gyro_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gyro_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gyro_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="samples")

    __table_args__ = (
        Index("idx_session_sample_ts", "session_id", "ts_ms"),
    )


class SpatialPointModel(Base):
    __tablename__ = "spatial_points"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    ts_ms: Mapped[int] = mapped_column(Integer, index=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    z: Mapped[float] = mapped_column(Float, nullable=False)
    distance: Mapped[float] = mapped_column(Float, nullable=False)
    intensity: Mapped[float] = mapped_column(Float, default=1.0)
    uncertainty: Mapped[float] = mapped_column(Float, default=0.05)  # estimated 5cm default uncertainty
    quality_flag: Mapped[str] = mapped_column(String(32), default="measured")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="points")

    __table_args__ = (
        Index("idx_session_point_ts", "session_id", "ts_ms"),
    )


class VisionDetectionModel(Base):
    __tablename__ = "vision_detections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[int] = mapped_column(Integer, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    box_x: Mapped[float] = mapped_column(Float)
    box_y: Mapped[float] = mapped_column(Float)
    box_w: Mapped[float] = mapped_column(Float)
    box_h: Mapped[float] = mapped_column(Float)
    est_distance_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spatial_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spatial_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spatial_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_approximate: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="detections")
