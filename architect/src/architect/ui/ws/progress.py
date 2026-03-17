"""WebSocket endpoint for real-time progress streaming from ExecuteEngine."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from architect.ui.engine_manager import EngineManager

router = APIRouter()
logger = logging.getLogger(__name__)

_HEARTBEAT_TIMEOUT = 60.0  # seconds before sending a heartbeat


@router.websocket("/ws/progress/{job_id}")
async def progress_ws(websocket: WebSocket, job_id: str) -> None:
    """Stream progress events for a running job from the engine's async queue."""
    await websocket.accept()
    logger.info("Progress WS connected: job_id=%s", job_id)

    manager: EngineManager = websocket.app.state.engine_manager
    queue = manager.get_queue(job_id)

    if not queue:
        await websocket.send_json({"type": "error", "message": "Job not found"})
        await websocket.close(code=4004)
        return

    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_TIMEOUT)
                await websocket.send_json(msg.model_dump())
                # Stop streaming on complete or error
                if msg.type in ("complete", "error"):
                    break
            except TimeoutError:
                # Send heartbeat to keep connection alive
                await websocket.send_json({"type": "heartbeat"})
        await websocket.close()
    except WebSocketDisconnect:
        logger.info("Progress WS disconnected: job_id=%s", job_id)
    except Exception:
        logger.exception("Progress WS error: job_id=%s", job_id)
        try:
            await websocket.close(code=1011)
        except Exception:  # noqa: BLE001
            pass
