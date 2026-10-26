import json
import logging
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from app.schemas.schemas import WSEvent

logger = logging.getLogger("echomap.websocket")

class ConnectionManager:
    def __init__(self):
        # Maps session_id to set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Global listeners (e.g. dashboards)
        self.global_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, session_id: str = "global"):
        await websocket.accept()
        if session_id == "global":
            self.global_connections.add(websocket)
        else:
            if session_id not in self.active_connections:
                self.active_connections[session_id] = set()
            self.active_connections[session_id].add(websocket)
        logger.info(f"WebSocket client connected to session: {session_id}")

    def disconnect(self, websocket: WebSocket, session_id: str = "global"):
        if session_id == "global":
            self.global_connections.discard(websocket)
        elif session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        logger.info(f"WebSocket client disconnected from session: {session_id}")

    async def broadcast(self, message: dict, session_id: str = "global"):
        """Sends a JSON-serializable message to clients subscribed to session_id and global listeners."""
        text = json.dumps(message)
        recipients = set(self.global_connections)
        if session_id in self.active_connections:
            recipients.update(self.active_connections[session_id])

        for connection in list(recipients):
            try:
                await connection.send_text(text)
            except Exception as e:
                logger.warning(f"Error sending message to websocket: {e}")
                self.disconnect(connection, session_id)

ws_manager = ConnectionManager()
