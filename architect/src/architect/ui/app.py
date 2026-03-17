"""FastAPI application factory for ARCHITECT web UI."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from architect.config import settings
from architect.core.exceptions import ArchitectBaseError
from architect.llm import LLMRouter
from architect.ui.engine_manager import EngineManager
from architect.ui.plan_session_manager import PlanSessionManager
from architect.ui.routes import (
    agents_router,
    diff_router,
    execute_router,
    plan_router,
    preview_router,
    settings_router,
    vibe_router,
)
from architect.ui.ws import progress_router, terminal_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ARCHITECT",
        version="2.0.0",
        description="Autonomous multi-agent coding orchestration system",
    )

    # Shared LLM router
    llm_router = LLMRouter(settings)

    # Engine manager — job registry for execute/diff/terminal endpoints
    app.state.engine_manager = EngineManager(llm_router)

    # Plan session manager — plan conversation registry
    app.state.plan_session_manager = PlanSessionManager(llm_router)

    # CORS — allow Vite dev server and Electron (file:// sends Origin: null)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "null"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handler for domain errors
    @app.exception_handler(ArchitectBaseError)
    async def architect_error_handler(
        _request: Request, exc: ArchitectBaseError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "detail": exc.detail},
        )

    # REST routes
    app.include_router(plan_router, prefix="/api/plan", tags=["plan"])
    app.include_router(vibe_router, prefix="/api/plan", tags=["vibe"])
    app.include_router(execute_router, prefix="/api/execute", tags=["execute"])
    app.include_router(agents_router, prefix="/api/execute", tags=["agents"])
    app.include_router(diff_router, prefix="/api/diff", tags=["diff"])
    app.include_router(preview_router, prefix="/api/preview", tags=["preview"])
    app.include_router(settings_router, prefix="/api/settings", tags=["settings"])

    # WebSocket routes
    app.include_router(progress_router, tags=["ws"])
    app.include_router(terminal_router, tags=["ws"])

    # Health check
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
