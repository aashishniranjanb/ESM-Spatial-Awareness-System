import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database_models import SessionModel, SensorSampleModel, SpatialPointModel, VisionDetectionModel
from app.schemas.schemas import SessionCreate, SensorSampleBase, SpatialPointBase, VisionDetectionBase

class SessionService:
    @staticmethod
    async def create_session(db: AsyncSession, create_in: SessionCreate) -> SessionModel:
        session_id = str(uuid.uuid4())
        session = SessionModel(
            id=session_id,
            name=create_in.name,
            source_mode=create_in.source_mode,
            status="created",
            notes=create_in.notes,
            calibration_config=create_in.calibration_config or {},
            sample_count=0,
            point_count=0,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def list_sessions(db: AsyncSession, limit: int = 50, offset: int = 0) -> List[SessionModel]:
        stmt = select(SessionModel).order_by(SessionModel.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_session(db: AsyncSession, session_id: str) -> Optional[SessionModel]:
        stmt = select(SessionModel).where(SessionModel.id == session_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_status(db: AsyncSession, session_id: str, status: str) -> Optional[SessionModel]:
        session = await SessionService.get_session(db, session_id)
        if not session:
            return None
        session.status = status
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def delete_session(db: AsyncSession, session_id: str) -> bool:
        session = await SessionService.get_session(db, session_id)
        if not session:
            return False
        await db.delete(session)
        await db.commit()
        return True

    @staticmethod
    async def add_sample(db: AsyncSession, session_id: str, sample: SensorSampleBase) -> SensorSampleModel:
        accel = sample.accel_m_s2
        gyro = sample.gyro_rad_s
        sample_db = SensorSampleModel(
            session_id=session_id,
            ts_ms=sample.ts_ms,
            distance_cm=sample.distance_cm,
            echo_valid=sample.echo_valid,
            accel_x=accel.x if accel else None,
            accel_y=accel.y if accel else None,
            accel_z=accel.z if accel else None,
            gyro_x=gyro.x if gyro else None,
            gyro_y=gyro.y if gyro else None,
            gyro_z=gyro.z if gyro else None,
        )
        db.add(sample_db)
        
        # Increment sample count
        stmt = (
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(sample_count=SessionModel.sample_count + 1)
        )
        await db.execute(stmt)
        await db.commit()
        await db.refresh(sample_db)
        return sample_db

    @staticmethod
    async def add_point(db: AsyncSession, session_id: str, point: SpatialPointBase) -> SpatialPointModel:
        point_db = SpatialPointModel(
            id=f"{session_id}-{point.id}",
            session_id=session_id,
            ts_ms=point.ts_ms,
            x=point.x,
            y=point.y,
            z=point.z,
            distance=point.distance,
            intensity=point.intensity,
            uncertainty=point.uncertainty,
            quality_flag=point.quality_flag,
        )
        db.add(point_db)
        
        # Increment point count
        stmt = (
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(point_count=SessionModel.point_count + 1)
        )
        await db.execute(stmt)
        await db.commit()
        await db.refresh(point_db)
        return point_db

    @staticmethod
    async def get_session_points(db: AsyncSession, session_id: str) -> List[SpatialPointModel]:
        stmt = select(SpatialPointModel).where(SpatialPointModel.session_id == session_id).order_by(SpatialPointModel.ts_ms.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_session_samples(db: AsyncSession, session_id: str) -> List[SensorSampleModel]:
        stmt = select(SensorSampleModel).where(SensorSampleModel.session_id == session_id).order_by(SensorSampleModel.ts_ms.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def add_detection(
        db: AsyncSession,
        session_id: str,
        detection_id: str,
        timestamp: int,
        label: str,
        confidence: float,
        box_x: float,
        box_y: float,
        box_w: float,
        box_h: float,
        est_distance_m: Optional[float] = None,
        spatial_x: Optional[float] = None,
        spatial_y: Optional[float] = None,
        spatial_z: Optional[float] = None,
        is_approximate: bool = True
    ) -> VisionDetectionModel:
        detection_db = VisionDetectionModel(
            id=f"{session_id}-{detection_id}",
            session_id=session_id,
            timestamp=timestamp,
            label=label,
            confidence=confidence,
            box_x=box_x,
            box_y=box_y,
            box_w=box_w,
            box_h=box_h,
            est_distance_m=est_distance_m,
            spatial_x=spatial_x,
            spatial_y=spatial_y,
            spatial_z=spatial_z,
            is_approximate=is_approximate
        )
        db.add(detection_db)
        await db.commit()
        await db.refresh(detection_db)
        return detection_db

    @staticmethod
    async def get_session_detections(db: AsyncSession, session_id: str) -> List[VisionDetectionModel]:
        stmt = select(VisionDetectionModel).where(VisionDetectionModel.session_id == session_id).order_by(VisionDetectionModel.timestamp.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_session_replay_stream(db: AsyncSession, session_id: str) -> List[Dict[str, Any]]:
        """
        Merge and time-order all session events (samples, spatial points, vision detections)
        into a unified, deterministic replay event stream.
        """
        samples = await SessionService.get_session_samples(db, session_id)
        points = await SessionService.get_session_points(db, session_id)
        detections = await SessionService.get_session_detections(db, session_id)

        events: List[Dict[str, Any]] = []

        for s in samples:
            events.append({
                "type": "sensor.sample",
                "timestamp_ms": s.ts_ms,
                "data": {
                    "v": 1,
                    "type": "sample",
                    "ts_ms": s.ts_ms,
                    "distance_cm": s.distance_cm,
                    "echo_valid": s.echo_valid,
                    "accel_m_s2": {"x": s.accel_x, "y": s.accel_y, "z": s.accel_z} if s.accel_x is not None else None,
                    "gyro_rad_s": {"x": s.gyro_x, "y": s.gyro_y, "z": s.gyro_z} if s.gyro_x is not None else None,
                }
            })

        for p in points:
            events.append({
                "type": "spatial.point",
                "timestamp_ms": p.ts_ms,
                "data": {
                    "id": p.id,
                    "ts_ms": p.ts_ms,
                    "x": p.x,
                    "y": p.y,
                    "z": p.z,
                    "distance": p.distance,
                    "intensity": p.intensity,
                    "uncertainty": p.uncertainty,
                    "quality_flag": p.quality_flag,
                }
            })

        for d in detections:
            events.append({
                "type": "vision.detection",
                "timestamp_ms": d.timestamp,
                "data": {
                    "id": d.id,
                    "timestamp": d.timestamp,
                    "label": d.label,
                    "confidence": d.confidence,
                    "box_normalized": {
                        "x": d.box_x,
                        "y": d.box_y,
                        "w": d.box_w,
                        "h": d.box_h
                    },
                    "est_distance_m": d.est_distance_m,
                    "spatial_coords": {
                        "x": d.spatial_x,
                        "y": d.spatial_y,
                        "z": d.spatial_z
                    } if d.spatial_x is not None else None,
                    "is_approximate": d.is_approximate,
                    "provenance": "estimated"
                }
            })

        # Sort chronologically by timestamp_ms
        events.sort(key=lambda ev: ev["timestamp_ms"])
        return events
