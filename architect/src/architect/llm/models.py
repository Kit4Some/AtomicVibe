"""LLM model configuration, purpose mapping, and fallback chains."""

from __future__ import annotations

from dataclasses import dataclass

from architect.llm.tiers import Tier, TIER_MAX_AGENTS, build_purpose_model_map


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Configuration for a specific LLM model."""

    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.0
    supports_structured_output: bool = True


# ---------------------------------------------------------------------------
# Current tier state
# ---------------------------------------------------------------------------

_current_tier: Tier = Tier.MID

PURPOSE_MODEL_MAP: dict[str, str] = build_purpose_model_map(_current_tier)


def set_tier(tier: Tier | str) -> None:
    """Update the active tier and rebuild PURPOSE_MODEL_MAP."""
    global _current_tier, PURPOSE_MODEL_MAP
    if isinstance(tier, str):
        tier = Tier(tier)
    _current_tier = tier
    PURPOSE_MODEL_MAP = build_purpose_model_map(tier)


def get_tier() -> Tier:
    """Return the current tier."""
    return _current_tier


def get_max_agents() -> int:
    """Return the max concurrent agents for the current tier."""
    return TIER_MAX_AGENTS[_current_tier]


# ---------------------------------------------------------------------------
# Fallback chains
# ---------------------------------------------------------------------------

FALLBACK_CHAINS: dict[str, list[str]] = {
    "claude-opus-4-6": ["claude-sonnet-4-6", "openai/gpt-4o"],
    "claude-sonnet-4-6": ["openai/gpt-4o", "deepseek/deepseek-chat"],
    "claude-haiku-4-5": ["openai/gpt-4o-mini"],
}

# ---------------------------------------------------------------------------
# Per-purpose default configs (temperature/max_tokens per purpose)
# ---------------------------------------------------------------------------

PURPOSE_CONFIGS: dict[str, ModelConfig] = {
    "plan_analysis": ModelConfig(
        model_name="dynamic", max_tokens=4096, temperature=0.0,
    ),
    "plan_choices": ModelConfig(
        model_name="dynamic", max_tokens=2048, temperature=0.7,
    ),
    "generate_md": ModelConfig(
        model_name="dynamic", max_tokens=8192, temperature=0.0,
    ),
    "code_generation": ModelConfig(
        model_name="dynamic", max_tokens=8192, temperature=0.0,
    ),
    "code_review": ModelConfig(
        model_name="dynamic", max_tokens=4096, temperature=0.0,
    ),
    "fix": ModelConfig(
        model_name="dynamic", max_tokens=8192, temperature=0.0,
    ),
    "diagnose": ModelConfig(
        model_name="dynamic", max_tokens=4096, temperature=0.0,
    ),
    "supervisor": ModelConfig(
        model_name="dynamic", max_tokens=2048, temperature=0.0,
    ),
    "strategize": ModelConfig(
        model_name="dynamic", max_tokens=4096, temperature=0.2,
    ),
}

# ---------------------------------------------------------------------------
# Model pricing (USD per 1 000 tokens) — fallback when litellm lookup fails
# ---------------------------------------------------------------------------

MODEL_PRICES: dict[str, tuple[float, float]] = {
    # (input_cost_per_1k, output_cost_per_1k)
    "claude-opus-4-6": (0.015, 0.075),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4-5": (0.001, 0.005),
    "openai/gpt-4o": (0.0025, 0.010),
    "openai/gpt-4o-mini": (0.00015, 0.0006),
    "deepseek/deepseek-chat": (0.00014, 0.00028),
}
