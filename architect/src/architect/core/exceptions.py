"""Exception hierarchy for ARCHITECT.

All exceptions inherit from ArchitectBaseError.
"""

from __future__ import annotations


class ArchitectBaseError(Exception):
    """Base exception for all ARCHITECT errors."""

    def __init__(
        self,
        message: str = "An error occurred",
        detail: str = "",
        status_code: int = 500,
    ) -> None:
        self.message = message
        self.detail = detail
        self.status_code = status_code
        super().__init__(message)


# ============================================================================
# Top-level domain errors
# ============================================================================


class PlanError(ArchitectBaseError):
    """Error during Plan Engine execution."""

    def __init__(self, message: str = "Plan error", detail: str = "", status_code: int = 400):
        super().__init__(message=message, detail=detail, status_code=status_code)


class GenerateError(ArchitectBaseError):
    """Error during Generate Engine execution."""

    def __init__(
        self, message: str = "Generate error", detail: str = "", status_code: int = 500
    ):
        super().__init__(message=message, detail=detail, status_code=status_code)


class ExecuteError(ArchitectBaseError):
    """Error during Execute Engine execution."""

    def __init__(
        self, message: str = "Execute error", detail: str = "", status_code: int = 500
    ):
        super().__init__(message=message, detail=detail, status_code=status_code)


class LLMError(ArchitectBaseError):
    """Error related to LLM operations."""

    def __init__(self, message: str = "LLM error", detail: str = "", status_code: int = 502):
        super().__init__(message=message, detail=detail, status_code=status_code)


class UIError(ArchitectBaseError):
    """Error in the UI layer."""

    def __init__(self, message: str = "UI error", detail: str = "", status_code: int = 500):
        super().__init__(message=message, detail=detail, status_code=status_code)


# ============================================================================
# LLMError subtypes
# ============================================================================


class LLMRateLimitError(LLMError):
    """LLM provider rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", detail: str = ""):
        super().__init__(message=message, detail=detail, status_code=429)


class LLMResponseParseError(LLMError):
    """Failed to parse LLM response into expected structure."""

    def __init__(self, message: str = "Failed to parse LLM response", detail: str = ""):
        super().__init__(message=message, detail=detail, status_code=502)


class LLMBudgetExceededError(LLMError):
    """LLM cost budget has been exceeded."""

    def __init__(self, message: str = "LLM budget exceeded", detail: str = ""):
        super().__init__(message=message, detail=detail, status_code=402)


# ============================================================================
# ExecuteError subtypes
# ============================================================================


class ValidationError(ExecuteError):
    """Code validation (lint, test, typecheck) failed."""

    def __init__(self, message: str = "Validation failed", detail: str = ""):
        super().__init__(message=message, detail=detail, status_code=422)


class DispatchError(ExecuteError):
    """Failed to dispatch a coding agent."""

    def __init__(self, message: str = "Agent dispatch failed", detail: str = ""):
        super().__init__(message=message, detail=detail, status_code=500)


class FixError(ExecuteError):
    """Failed to apply a fix strategy."""

    def __init__(self, message: str = "Fix failed", detail: str = ""):
        super().__init__(message=message, detail=detail, status_code=500)


class WorkspaceError(ExecuteError):
    """Error in workspace file operations or git."""

    def __init__(self, message: str = "Workspace error", detail: str = ""):
        super().__init__(message=message, detail=detail, status_code=500)
