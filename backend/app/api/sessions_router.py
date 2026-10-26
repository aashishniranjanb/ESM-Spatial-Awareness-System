import csv
import io
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.schemas.schemas import (
    SessionCreate, SessionResponse, SessionDetailResponse,
    SensorSampleResponse, SpatialPointResponse, SensorSampleBase
)
from app.services.session_service import SessionService
from app.spatial.pipeline import SpatialPipeline

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(data: SessionCreate, db: AsyncSession = Depends(get_db)):
    session = await SessionService.create_session(db, data)
    return session

@router.get("", response_model=List[SessionResponse])
async def list_sessions(limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    return await SessionService.list_sessions(db, limit=limit, offset=offset)

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await SessionService.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await SessionService.delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)

@router.post("/{session_id}/samples", response_model=SensorSampleResponse)
async def ingest_sample(session_id: str, sample: SensorSampleBase, db: AsyncSession = Depends(get_db)):
    session = await SessionService.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    sample_model = await SessionService.add_sample(db, session_id, sample)
    
    # Transform sample into spatial point if valid
    pipeline = SpatialPipeline()
    point, _ = pipeline.project_sample(sample)
    if point:
        await SessionService.add_point(db, session_id, point)

    return sample_model

@router.get("/{session_id}/points", response_model=List[SpatialPointResponse])
async def get_session_points(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await SessionService.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return await SessionService.get_session_points(db, session_id)

@router.get("/{session_id}/samples", response_model=List[SensorSampleResponse])
async def get_session_samples(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await SessionService.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return await SessionService.get_session_samples(db, session_id)

@router.get("/{session_id}/replay")
async def get_session_replay(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await SessionService.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    events = await SessionService.get_session_replay_stream(db, session_id)
    return {
        "session": {
            "id": session.id,
            "name": session.name,
            "source_mode": session.source_mode,
            "status": session.status,
            "sample_count": session.sample_count,
            "point_count": session.point_count,
            "created_at": session.created_at.isoformat()
        },
        "event_count": len(events),
        "events": events
    }

@router.get("/{session_id}/export/json")
async def export_json(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await SessionService.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    points = await SessionService.get_session_points(db, session_id)
    samples = await SessionService.get_session_samples(db, session_id)

    payload = {
        "format": "echomap-scan-v2",
        "session": {
            "id": session.id,
            "name": session.name,
            "source_mode": session.source_mode,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
            "sample_count": session.sample_count,
            "point_count": session.point_count,
        },
        "points": [
            {
                "id": p.id,
                "x": p.x,
                "y": p.y,
                "z": p.z,
                "distance": p.distance,
                "intensity": p.intensity,
                "uncertainty": p.uncertainty,
                "quality_flag": p.quality_flag
            } for p in points
        ],
        "samples": [
            {
                "ts_ms": s.ts_ms,
                "distance_cm": s.distance_cm,
                "echo_valid": s.echo_valid,
                "accel": {"x": s.accel_x, "y": s.accel_y, "z": s.accel_z} if s.accel_x is not None else None,
                "gyro": {"x": s.gyro_x, "y": s.gyro_y, "z": s.gyro_z} if s.gyro_x is not None else None
            } for s in samples
        ]
    }
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=echomap-{session_id}.json"}
    )

@router.get("/{session_id}/export/csv")
async def export_csv(session_id: str, db: AsyncSession = Depends(get_db)):
    points = await SessionService.get_session_points(db, session_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "ts_ms", "x", "y", "z", "distance_m", "intensity", "uncertainty", "quality_flag"])
    for p in points:
        writer.writerow([p.id, p.ts_ms, p.x, p.y, p.z, p.distance, p.intensity, p.uncertainty, p.quality_flag])
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=echomap-points-{session_id}.csv"}
    )

@router.get("/{session_id}/map/export")
async def export_map(session_id: str, db: AsyncSession = Depends(get_db)):
    """Export the persistent map state for a session."""
    session = await SessionService.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    from app.websocket.ws_router import session_maps
    map_state = session_maps.get(session_id)
    if not map_state:
        return {"format": "esm-map-v1", "session_id": session_id, "landmarks": [], "message": "No active map for this session"}
    
    return map_state.export_map()

@router.post("/{session_id}/map/reset", status_code=200)
async def reset_map(session_id: str, db: AsyncSession = Depends(get_db)):
    """Reset the map state for a session. Does NOT delete the session or its stored data."""
    session = await SessionService.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    from app.websocket.ws_router import session_maps
    map_state = session_maps.get(session_id)
    if map_state:
        map_state.reset()
    
    return {"status": "ok", "message": f"Map reset for session {session_id}. Session data preserved."}

