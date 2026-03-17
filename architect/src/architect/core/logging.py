"""Structured logging configuration for ARCHITECT using structlog."""

from __future__ import annotations

import os
import sys

import structlog


def _configure_structlog(log_format: str = "console") -> None:
    """Configure structlog processors based on output format."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


_configured = False


def _ensure_configured() -> None:
    """Ensure structlog is configured exactly once."""
    global _configured  # noqa: PLW0603
    if not _configured:
        log_format = os.environ.get("ARCHITECT_LOG_FORMAT", "console")
        _configure_structlog(log_format)
        _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named structured logger.

    Args:
        name: Logger name, typically the module name.

    Returns:
        A bound structlog logger instance.
    """
    _ensure_configured()
    return structlog.get_logger(name)


def reconfigure(log_format: str) -> None:
    """Reconfigure logging format at runtime.

    Args:
        log_format: Either "json" or "console".
    """
    global _configured  # noqa: PLW0603
    _configured = False
    os.environ["ARCHITECT_LOG_FORMAT"] = log_format
    _ensure_configured()
