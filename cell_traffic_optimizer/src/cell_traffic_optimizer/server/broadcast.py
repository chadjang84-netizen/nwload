"""WebSocket broadcast helpers."""
from __future__ import annotations
import asyncio
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import AppState

logger = logging.getLogger(__name__)


async def broadcast(state: AppState, message: dict) -> None:
    if not state.websocket_clients:
        return
    text = json.dumps(message, ensure_ascii=False)
    dead = set()
    for ws in list(state.websocket_clients):
        try:
            await ws.send_text(text)
        except Exception:
            dead.add(ws)
    state.websocket_clients -= dead
