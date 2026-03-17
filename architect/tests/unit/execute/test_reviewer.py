"""Unit tests for supervisor/reviewer.py — review_code."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from architect.core.models import ReviewResult
from architect.execute.supervisor.reviewer import review_code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_review(
    score: float = 4.2,
    critical: list[str] | None = None,
) -> ReviewResult:
    return ReviewResult(
        overall_score=score,
        dimensions={
            "interface_compliance": {"score": 5, "issues": []},
            "convention_adherence": {"score": 4, "issues": []},
            "architecture_consistency": {"score": 4, "issues": []},
            "implementation_quality": {"score": 4, "issues": []},
            "security": {"score": 5, "issues": []},
            "testability": {"score": 3, "issues": ["Happy path only"]},
        },
        critical_issues=critical or [],
        suggestions=["Add timeout to connection"],
        revision_instructions="Add error case test.",
    )


_CODE = {"src/main.py": "def main():\n    print('hello')\n"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_review_code_returns_review_result() -> None:
    """Verify review_code returns a ReviewResult."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_review())

    result = await review_code(
        code_files=_CODE,
        interfaces_md="# Interfaces",
        conventions_md="# Conventions",
        spec_md="# Spec",
        llm=mock_llm,
    )

    assert isinstance(result, ReviewResult)
    assert result.overall_score == 4.2


@pytest.mark.asyncio()
async def test_review_code_passes_when_score_above_threshold() -> None:
    """Score >= 3.5 and no critical issues → passed=True."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_review(score=4.0))

    result = await review_code(
        code_files=_CODE,
        interfaces_md="",
        conventions_md="",
        spec_md="",
        llm=mock_llm,
    )

    assert result.passed is True


@pytest.mark.asyncio()
async def test_review_code_fails_when_critical_issues_present() -> None:
    """Even with high score, critical issues → passed=False."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(
        return_value=_sample_review(score=4.0, critical=["Broken interface"])
    )

    result = await review_code(
        code_files=_CODE,
        interfaces_md="",
        conventions_md="",
        spec_md="",
        llm=mock_llm,
    )

    assert result.passed is False
    assert len(result.critical_issues) == 1


@pytest.mark.asyncio()
async def test_review_code_fails_when_score_below_threshold() -> None:
    """Score < 3.5 → passed=False."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_review(score=2.5))

    result = await review_code(
        code_files=_CODE,
        interfaces_md="",
        conventions_md="",
        spec_md="",
        llm=mock_llm,
    )

    assert result.passed is False


@pytest.mark.asyncio()
async def test_review_code_calls_llm_with_code_review_purpose() -> None:
    """Verify purpose='code_review'."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_review())

    await review_code(
        code_files=_CODE,
        interfaces_md="",
        conventions_md="",
        spec_md="",
        llm=mock_llm,
    )

    call_kwargs = mock_llm.complete_structured.call_args
    assert call_kwargs.kwargs["purpose"] == "code_review"
    assert call_kwargs.kwargs["response_model"] is ReviewResult


@pytest.mark.asyncio()
async def test_review_code_includes_all_files_in_prompt() -> None:
    """Verify all code files appear in the user message."""
    mock_llm = AsyncMock()
    mock_llm.complete_structured = AsyncMock(return_value=_sample_review())

    files = {"a.py": "# a", "b.py": "# b"}
    await review_code(
        code_files=files,
        interfaces_md="",
        conventions_md="",
        spec_md="",
        llm=mock_llm,
    )

    messages = mock_llm.complete_structured.call_args.kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "a.py" in user_msg["content"]
    assert "b.py" in user_msg["content"]
