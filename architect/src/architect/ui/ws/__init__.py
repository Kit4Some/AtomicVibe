"""UI WebSocket route routers."""

from architect.ui.ws.progress import router as progress_router
from architect.ui.ws.terminal import router as terminal_router

__all__ = ["progress_router", "terminal_router"]
