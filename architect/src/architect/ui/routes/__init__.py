"""UI REST API route routers."""

from architect.ui.routes.agents import router as agents_router
from architect.ui.routes.diff import router as diff_router
from architect.ui.routes.execute import router as execute_router
from architect.ui.routes.plan import router as plan_router
from architect.ui.routes.preview import router as preview_router
from architect.ui.routes.settings import router as settings_router
from architect.ui.routes.vibe import router as vibe_router

__all__ = [
    "agents_router",
    "diff_router",
    "execute_router",
    "plan_router",
    "preview_router",
    "settings_router",
    "vibe_router",
]
