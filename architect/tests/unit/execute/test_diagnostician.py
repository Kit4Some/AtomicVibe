"""Unit tests for supervisor/diagnostician.py — diagnose."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from architect.core.models import DiagnosisResult
from architect.execute.supervisor.diagnostician import diagnose


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_diagnosis() -> DiagnosisResult:
    return DiagnosisResult(
        surface_error="ImportError: cannot import name 'LLMRouter'",
        root_cause="__init__.py does not export LLMRouter",
        error_category="import",
        severity="blocking",
        seen_before=True,
        occurrence_count=2,
        recommendation={
            "approach": "apply_known_fix",
            "fix_description": "Use direct import from module",
            "confidence": 0.9,
            "fallback": "Check __init__.py manually",
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_diagnose_returns_diagnosis_result() -> None:
    """Verify diagnose returns a DiagnosisResult."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_diagnosis())

    result = await diagnose(
        errors=[{"message": "ImportError"}],
        error_history=[],
        knowledge_base=[],
        code_context={"main.py": "from llm import LLMRouter"},
        llm=mock_llm,
    )

    assert isinstance(result, DiagnosisResult)
    assert result.error_category == "import"
    assert result.severity == "blocking"


@pytest.mark.asyncio()
async def test_diagnose_calls_llm_with_diagnose_purpose() -> None:
    """Verify purpose='diagnose'."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_diagnosis())

    await diagnose(
        errors=[{"message": "TypeError"}],
        error_history=[],
        knowledge_base=[],
        code_context={},
        llm=mock_llm,
    )

    call_kwargs = mock_llm.complete_structured.call_args
    assert call_kwargs.kwargs["purpose"] == "diagnose"
    assert call_kwargs.kwargs["response_model"] is DiagnosisResult


@pytest.mark.asyncio()
async def test_diagnose_includes_errors_in_prompt() -> None:
    """Verify error data appears in the user message."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_diagnosis())

    await diagnose(
        errors=[{"message": "NameError: x is not defined"}],
        error_history=[],
        knowledge_base=[],
        code_context={},
        llm=mock_llm,
    )

    messages = mock_llm.complete_structured.call_args.kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "NameError" in user_msg["content"]


@pytest.mark.asyncio()
async def test_diagnose_includes_knowledge_in_prompt() -> None:
    """Verify knowledge base entries appear in the user message."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_diagnosis())

    kb = [{"problem": "init export issue", "solution": "add to __all__"}]
    await diagnose(
        errors=[{"message": "ImportError"}],
        error_history=[],
        knowledge_base=kb,
        code_context={},
        llm=mock_llm,
    )

    messages = mock_llm.complete_structured.call_args.kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "init export" in user_msg["content"]


@pytest.mark.asyncio()
async def test_diagnose_empty_errors_returns_cosmetic() -> None:
    """Empty errors list → cosmetic result without LLM call."""
    mock_llm = AsyncMock()

    result = await diagnose(
        errors=[],
        error_history=[],
        knowledge_base=[],
        code_context={},
        llm=mock_llm,
    )

    assert result.severity == "cosmetic"
    assert result.seen_before is False
    mock_llm.complete_structured.assert_not_called()
