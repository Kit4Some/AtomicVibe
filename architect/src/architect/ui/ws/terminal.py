"""WebSocket endpoint for bidirectional terminal (subprocess pty)."""

from __future__ import annotations

import asyncio
import logging
import sys

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from architect.config import settings
from architect.ui.engine_manager import EngineManager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/terminal/{job_id}")
async def terminal_ws(websocket: WebSocket, job_id: str) -> None:
    """Bidirectional terminal: WebSocket ↔ subprocess."""
    await websocket.accept()
    logger.info("Terminal WS connected: job_id=%s", job_id)

    shell = "cmd.exe" if sys.platform == "win32" else "/bin/bash"

    # Resolve workspace directory for the shell's cwd
    manager: EngineManager = websocket.app.state.engine_manager
    cwd = manager.get_workspace_path(job_id) or str(settings.workspace_path)

    try:
        proc = await asyncio.create_subprocess_exec(
            shell,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
    except OSError:
        logger.exception("Failed to spawn shell: %s", shell)
        await websocket.close(code=1011)
        return

    async def _ws_to_proc() -> None:
        """Forward WebSocket input to subprocess stdin."""
        try:
            while True:
                data = await websocket.receive_text()
                if proc.stdin and not proc.stdin.is_closing():
                    proc.stdin.write(data.encode())
                    await proc.stdin.drain()
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("ws_to_proc error")

    async def _proc_to_ws() -> None:
        """Forward subprocess stdout to WebSocket."""
        try:
            assert proc.stdout is not None
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                await websocket.send_text(chunk.decode(errors="replace"))
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("proc_to_ws error")

    ws_task = asyncio.create_task(_ws_to_proc())
    proc_task = asyncio.create_task(_proc_to_ws())

    try:
        done, pending = await asyncio.wait(
            {ws_task, proc_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except TimeoutError:
                proc.kill()
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("Terminal WS closed: job_id=%s", job_id)
