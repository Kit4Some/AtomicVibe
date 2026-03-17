"""Tier system — maps quality tiers to Claude model selections per role."""

from __future__ import annotations

from enum import Enum


class Tier(str, Enum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"
    MAX = "max"


# Role → model per tier
TIER_MODEL_MAP: dict[Tier, dict[str, str]] = {
    Tier.LOW: {
        "thinking": "claude-haiku-4-5",
        "code_write": "claude-haiku-4-5",
        "code_qa": "claude-haiku-4-5",
    },
    Tier.MID: {
        "thinking": "claude-sonnet-4-6",
        "code_write": "claude-haiku-4-5",
        "code_qa": "claude-sonnet-4-6",
    },
    Tier.HIGH: {
        "thinking": "claude-opus-4-6",
        "code_write": "claude-haiku-4-5",
        "code_qa": "claude-opus-4-6",
    },
    Tier.MAX: {
        "thinking": "claude-opus-4-6",
        "code_write": "claude-sonnet-4-6",
        "code_qa": "claude-opus-4-6",
    },
}

# Max concurrent agents per tier
TIER_MAX_AGENTS: dict[Tier, int] = {
    Tier.LOW: 3,
    Tier.MID: 5,
    Tier.HIGH: 8,
    Tier.MAX: 10,
}

# Maps each LLM purpose to its role
PURPOSE_TO_ROLE: dict[str, str] = {
    "plan_analysis": "thinking",
    "plan_choices": "thinking",
    "generate_md": "thinking",
    "supervisor": "thinking",
    "strategize": "thinking",
    "diagnose": "thinking",
    "code_generation": "code_write",
    "fix": "code_write",
    "code_review": "code_qa",
}


def get_model_for_purpose(tier: Tier, purpose: str) -> str:
    """Return the model ID for a given tier and purpose."""
    role = PURPOSE_TO_ROLE.get(purpose, "thinking")
    return TIER_MODEL_MAP[tier][role]


def build_purpose_model_map(tier: Tier) -> dict[str, str]:
    """Build a complete purpose → model dict for the given tier."""
    return {purpose: get_model_for_purpose(tier, purpose) for purpose in PURPOSE_TO_ROLE}
