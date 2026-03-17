"""Settings REST API routes — API key management and tier selection."""

from __future__ import annotations

import logging
from pathlib import Path

import litellm
from fastapi import APIRouter, Request

from architect.config import get_settings
from architect.llm.models import get_max_agents, get_tier, set_tier
from architect.llm.tiers import TIER_MAX_AGENTS, Tier
from architect.ui.schemas import (
    ApiKeyRequest,
    ApiKeyResponse,
    SettingsResponse,
    TierRequest,
    TierResponse,
)

router = APIRouter()
log = logging.getLogger("architect.ui.routes.settings")

# Path to .env file (project root)
_ENV_FILE = Path(".env")


def _is_api_key_configured() -> bool:
    """Check whether an Anthropic API key is set and non-empty."""
    s = get_settings()
    return bool(s.anthropic_api_key.get_secret_value())


def _persist_env(key: str, value: str) -> None:
    """Write or update a key=value pair in the .env file."""
    lines: list[str] = []
    found = False

    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)

    if not found:
        lines.append(f"{key}={value}")

    _ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


@router.get("", response_model=SettingsResponse)
async def get_current_settings() -> SettingsResponse:
    """Return current settings state."""
    return SettingsResponse(
        tier=get_tier().value,
        api_key_configured=_is_api_key_configured(),
        max_agents=get_max_agents(),
    )


@router.post("/api-key", response_model=ApiKeyResponse)
async def set_api_key(body: ApiKeyRequest, request: Request) -> ApiKeyResponse:
    """Validate and save an Anthropic API key."""
    key = body.key.strip()

    # Validate by making a minimal test call
    try:
        await litellm.acompletion(
            model="claude-haiku-4-5",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            api_key=key,
        )
    except litellm.AuthenticationError:
        return ApiKeyResponse(valid=False, message="Invalid API key.")
    except Exception as exc:
        log.warning("API key validation error: %s", exc)
        return ApiKeyResponse(valid=False, message=f"Validation failed: {exc}")

    # Persist to .env
    _persist_env("ARCHITECT_ANTHROPIC_API_KEY", key)

    # Update runtime config — clear lru_cache and re-init LLM router
    get_settings.cache_clear()
    settings = get_settings()
    litellm.api_key = key

    # Re-create the LLM router on app state
    from architect.llm import LLMRouter

    new_router = LLMRouter(settings)
    request.app.state.engine_manager._llm = new_router
    request.app.state.plan_session_manager._llm = new_router

    log.info("API key updated and validated successfully")
    return ApiKeyResponse(valid=True, message="API key saved successfully.")


@router.post("/tier", response_model=TierResponse)
async def set_tier_endpoint(body: TierRequest) -> TierResponse:
    """Change the active quality tier."""
    tier = Tier(body.tier)
    set_tier(tier)

    # Persist to .env
    _persist_env("ARCHITECT_TIER", tier.value)

    log.info("Tier changed to %s (max_agents=%d)", tier.value, TIER_MAX_AGENTS[tier])
    return TierResponse(tier=tier.value, max_agents=TIER_MAX_AGENTS[tier])
