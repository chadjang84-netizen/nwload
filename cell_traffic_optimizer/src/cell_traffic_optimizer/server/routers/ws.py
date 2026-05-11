from __future__ import annotations
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..deps import get_state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    state = get_state(websocket)
    await websocket.accept()
    state.websocket_clients.add(websocket)
    logger.info("WebSocket client connected (%d total)", len(state.websocket_clients))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        state.websocket_clients.discard(websocket)
        logger.info("WebSocket client disconnected (%d remaining)", len(state.websocket_clients))
