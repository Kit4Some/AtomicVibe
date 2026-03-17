"""Test configuration for Plan Engine tests."""

from __future__ import annotations

import structlog

import architect.core.logging as _logging_mod


def pytest_configure() -> None:
    """Configure structlog for test environment without add_logger_name."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    # Mark as already configured so core.logging doesn't reconfigure
    _logging_mod._configured = True
