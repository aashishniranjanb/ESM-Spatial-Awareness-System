import asyncio
import base64
import json
import logging
import time
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.connection_manager import ws_manager
from app.schemas.schemas import (
    SensorSampleBase,
    SpatialPointBase,
    VisionDetectionExtended,
    VisionStatusEvent,
    PathCorridorConfig
)
from app.services.session_service import SessionService
from app.spatial.pipeline import SpatialPipeline
from app.vision.yolo_pipeline import YOLOTrackingPipeline
from app.vision.association import SensorVisionAssociationEngine
from app.database.session import AsyncSessionLocal
from app.mapping.map_state import PersistentMapState
from app.mapping.slam_interface import UnavailableSLAMBackend

logger = logging.getLogger("esm.ws_router")
router = APIRouter(tags=["websocket"])

# Spatial pipelines keyed by session_id
session_pipelines: Dict[str, SpatialPipeline] = {}

# Persistent map states per session
session_maps: Dict[str, PersistentMapState] = {}

# SLAM backend (explicitly reports unavailable)
slam_backend = UnavailableSLAMBackend()

# Latest sensor sample cache for heuristic association
latest_sensor_samples: Dict[str, SensorSampleBase] = {}

# Shared Vision Inference Pipeline
vision_pipeline = YOLOTrackingPipeline()
association_engine = SensorVisionAssociationEngine()

# ThreadPoolExecutor to prevent blocking FastAPI async event loop with YOLO inference
vision_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="esm_yolo_worker")

# Bounded queue / latency throttling tracker per session
last_frame_processed_time: Dict[str, float] = {}
FRAME_PROCESSING_MIN_INTERVAL = 0.10  # Max 10 FPS to ensure laptop CPU stability

@router.websocket("/ws")
@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str = "global"):
    await ws_manager.connect(websocket, session_id)
    if session_id not in session_pipelines:
        session_pipelines[session_id] = SpatialPipeline()

    pipeline = session_pipelines[session_id]

    if session_id not in session_maps:
        session_maps[session_id] = PersistentMapState(session_id)
    map_state = session_maps[session_id]

    # Send initial vision status to connecting client
    status_msg = {
        "event": "vision.status",
        "session_id": session_id,
        "payload": vision_pipeline.get_status().model_dump()
    }
    await websocket.send_text(json.dumps(status_msg))

    # Send SLAM status (explicitly unavailable)
    slam_status_msg = {
        "event": "slam.status",
        "session_id": session_id,
        "payload": {
            "state": slam_backend.get_status().state.value,
            "engine_name": slam_backend.get_name(),
            "available": slam_backend.is_available(),
            "message": slam_backend.get_status().last_error,
        }
    }
    await websocket.send_text(json.dumps(slam_status_msg))

    try:
        while True:
            # Handle both Text frames (JSON control/sensor messages) and Binary frames (Camera images)
            message = await websocket.receive()
            
            if "text" in message:
                data_text = message["text"]
                try:
                    msg = json.loads(data_text)
                except Exception:
                    await websocket.send_text(json.dumps({"event": "error", "message": "Invalid JSON"}))
                    continue

                event_type = msg.get("event")
                payload = msg.get("payload", {})
                msg_session_id = msg.get("session_id") or session_id

                if event_type == "ping":
                    await websocket.send_text(json.dumps({"event": "pong", "timestamp": msg.get("timestamp")}))
                    continue

                elif event_type == "sensor.sample":
                    try:
                        sample = SensorSampleBase(**payload)
                    except Exception as e:
                        await websocket.send_text(json.dumps({"event": "error", "message": f"Malformed sample: {str(e)}"}))
                        continue

                    # Cache latest valid sample for heuristic vision correlation
                    latest_sensor_samples[msg_session_id] = sample

                    # Process spatial projection
                    point, filter_reason = pipeline.project_sample(sample)

                    # Persist to DB if attached to a valid session
                    if msg_session_id != "global":
                        async with AsyncSessionLocal() as db:
                            try:
                                await SessionService.add_sample(db, msg_session_id, sample)
                                if point:
                                    await SessionService.add_point(db, msg_session_id, point)
                            except Exception as ex:
                                logger.error(f"Error persisting sample to session {msg_session_id}: {ex}")

                    # Broadcast sample event
                    await ws_manager.broadcast({
                        "event": "sensor.sample",
                        "session_id": msg_session_id,
                        "payload": payload
                    }, msg_session_id)

                    # Broadcast derived point if valid
                    if point:
                        # Add point as measured landmark in persistent map
                        map_state.add_ultrasonic_landmark(
                            point_id=point.id,
                            x=point.x,
                            y=point.y,
                            z=point.z,
                            distance_m=point.distance,
                            uncertainty=point.uncertainty,
                            frame_id=map_state.current_frame_id,
                            timestamp_ms=sample.ts_ms
                        )

                        await ws_manager.broadcast({
                            "event": "spatial.point",
                            "session_id": msg_session_id,
                            "payload": point.model_dump()
                        }, msg_session_id)

                elif event_type == "vision.frame":
                    # Fallback base64 image transmission
                    img_b64 = payload.get("image_base64")
                    frame_id = payload.get("frame_id", 0)
                    if img_b64:
                        try:
                            # Drop frame if previous frame was processed too recently (backpressure)
                            now = time.time()
                            if now - last_frame_processed_time.get(msg_session_id, 0) < FRAME_PROCESSING_MIN_INTERVAL:
                                continue
                            last_frame_processed_time[msg_session_id] = now

                            raw_bytes = base64.b64decode(img_b64.split(",")[-1])
                            loop = asyncio.get_running_loop()
                            detections, latency = await loop.run_in_executor(
                                vision_executor,
                                vision_pipeline.process_frame,
                                raw_bytes,
                                frame_id,
                                msg_session_id
                            )

                            # Evaluate heuristic association with latest ultrasonic sample
                            latest_sample = latest_sensor_samples.get(msg_session_id)
                            detections = association_engine.evaluate_association(latest_sample, detections)

                            # Broadcast vision detections to session
                            await ws_manager.broadcast({
                                "event": "vision.detection",
                                "session_id": msg_session_id,
                                "payload": {
                                    "frame_id": frame_id,
                                    "detections": [d.dict() for d in detections],
                                    "latency_ms": latency,
                                    "status": vision_pipeline.get_status().dict()
                                }
                            }, msg_session_id)

                            # Persist detections if linked to an active session
                            if msg_session_id != "global" and detections:
                                async with AsyncSessionLocal() as db:
                                    try:
                                        for d in detections:
                                            await SessionService.add_detection(
                                                db=db,
                                                session_id=msg_session_id,
                                                detection_id=d.id,
                                                timestamp=d.timestamp_ms,
                                                label=d.class_name,
                                                confidence=d.confidence,
                                                box_x=d.box_normalized.x,
                                                box_y=d.box_normalized.y,
                                                box_w=d.box_normalized.w,
                                                box_h=d.box_normalized.h,
                                                est_distance_m=d.acoustic_candidate_dist_m,
                                                spatial_x=(d.box_normalized.x + d.box_normalized.w / 2 - 0.5) * 2.0,
                                                spatial_y=-(d.box_normalized.y + d.box_normalized.h / 2 - 0.5) * 1.5,
                                                spatial_z=-(d.acoustic_candidate_dist_m or 2.5),
                                                is_approximate=True
                                            )
                                    except Exception as ex:
                                        logger.error(f"Error persisting vision detections for {msg_session_id}: {ex}")
                        except Exception as e:
                            logger.error(f"Error handling base64 vision frame: {e}")

                elif event_type == "vision.config":
                    # Update vision pipeline thresholds dynamically
                    if "conf_thresh" in payload:
                        vision_pipeline.conf_thresh = float(payload["conf_thresh"])
                    if "iou_thresh" in payload:
                        vision_pipeline.iou_thresh = float(payload["iou_thresh"])
                    if "corridor" in payload:
                        vision_pipeline.path_analyzer.update_config(PathCorridorConfig(**payload["corridor"]))

                    await websocket.send_text(json.dumps({
                        "event": "vision.status",
                        "session_id": msg_session_id,
                        "payload": vision_pipeline.get_status().dict()
                    }))

                elif event_type == "session.reset_pose":
                    pipeline.reset()
                    await ws_manager.broadcast({
                        "event": "session.pose_reset",
                        "session_id": msg_session_id,
                        "payload": {"status": "ok"}
                    }, msg_session_id)

                elif event_type == "map.reset":
                    map_state.reset()
                    pipeline.reset()
                    await ws_manager.broadcast({
                        "event": "map.reset",
                        "session_id": msg_session_id,
                        "payload": {"status": "ok", "map_status": map_state.get_status()}
                    }, msg_session_id)

                elif event_type == "map.status":
                    await websocket.send_text(json.dumps({
                        "event": "map.status",
                        "session_id": msg_session_id,
                        "payload": {
                            "map": map_state.get_status(),
                            "slam": {
                                "state": slam_backend.get_status().state.value,
                                "engine_name": slam_backend.get_name(),
                                "available": slam_backend.is_available(),
                            }
                        }
                    }))

            elif "bytes" in message:
                # High-throughput binary frame transport: header (8 bytes: 4B frame_id, 4B timestamp_ms) + JPEG payload
                bin_data = message["bytes"]
                if len(bin_data) > 8:
                    now = time.time()
                    if now - last_frame_processed_time.get(session_id, 0) < FRAME_PROCESSING_MIN_INTERVAL:
                        continue
                    last_frame_processed_time[session_id] = now

                    # Decode binary header
                    import struct
                    frame_id, ts_ms = struct.unpack("<II", bin_data[:8])
                    img_bytes = bin_data[8:]

                    loop = asyncio.get_running_loop()
                    detections, latency = await loop.run_in_executor(
                        vision_executor,
                        vision_pipeline.process_frame,
                        img_bytes,
                        frame_id,
                        session_id
                    )

                    latest_sample = latest_sensor_samples.get(session_id)
                    detections = association_engine.evaluate_association(latest_sample, detections)

                    await ws_manager.broadcast({
                        "event": "vision.detection",
                        "session_id": session_id,
                        "payload": {
                            "frame_id": frame_id,
                            "detections": [d.dict() for d in detections],
                            "latency_ms": latency,
                            "status": vision_pipeline.get_status().dict()
                        }
                    }, session_id)

                    # Persist detections if linked to an active session
                    if session_id != "global" and detections:
                        async with AsyncSessionLocal() as db:
                            try:
                                for d in detections:
                                    await SessionService.add_detection(
                                        db=db,
                                        session_id=session_id,
                                        detection_id=d.id,
                                        timestamp=ts_ms,
                                        label=d.class_name,
                                        confidence=d.confidence,
                                        box_x=d.box_normalized.x,
                                        box_y=d.box_normalized.y,
                                        box_w=d.box_normalized.w,
                                        box_h=d.box_normalized.h,
                                        est_distance_m=d.acoustic_candidate_dist_m,
                                        spatial_x=(d.box_normalized.x + d.box_normalized.w / 2 - 0.5) * 2.0,
                                        spatial_y=-(d.box_normalized.y + d.box_normalized.h / 2 - 0.5) * 1.5,
                                        spatial_z=-(d.acoustic_candidate_dist_m or 2.5),
                                        is_approximate=True
                                    )
                            except Exception as ex:
                                logger.error(f"Error persisting binary frame detections for {session_id}: {ex}")

                    # Update persistent map with tracked detections
                    map_state.current_frame_id = frame_id
                    for d in detections:
                        if d.track_id is not None:
                            map_state.update_object_track(
                                track_id=d.track_id,
                                class_name=d.class_name,
                                class_id=d.class_id,
                                box_normalized=d.box_normalized.model_dump(),
                                confidence=d.confidence,
                                frame_id=frame_id,
                                timestamp_ms=ts_ms,
                                acoustic_dist_m=d.acoustic_candidate_dist_m
                            )
                    map_state.mark_stale_entries(frame_id)

                    # Throttled map update broadcast (every 5th frame)
                    if frame_id % 5 == 0:
                        await ws_manager.broadcast({
                            "event": "map.update",
                            "session_id": session_id,
                            "payload": {
                                "landmarks": map_state.get_all_landmarks_serializable(),
                                "active_tracks": map_state.get_active_tracks_serializable(),
                                "map_status": map_state.get_status(),
                            }
                        }, session_id)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"Unexpected websocket error: {e}")
        ws_manager.disconnect(websocket, session_id)
