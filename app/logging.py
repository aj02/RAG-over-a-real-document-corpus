"""Structured JSON logging with request_id correlation.

structlog feeds events through a pipeline of processors that:
  1. attach contextvars (request_id, route, etc.)
  2. add timestamp + log level
  3. render to JSON for ingestion by log aggregators

Use ``bind_request_context`` from middleware so every log line in a request
shares the same request_id.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from structlog.types import EventDict, Processor

from app.config import get_settings


def _drop_color_message(_: Any, __: str, event_dict: EventDict) -> EventDict:
    # uvicorn injects a `color_message` we never want in JSON output.
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level, logging.INFO)

    # Note: ``structlog.stdlib.add_logger_name`` is intentionally absent —
    # it requires the wrapped logger to expose a ``.name`` attribute, which
    # PrintLoggerFactory's PrintLogger does not. If we ever switch to the
    # stdlib factory, add it back to the chain.
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _drop_color_message,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (uvicorn, sqlalchemy, etc.) through structlog so
    # everything ends up in one JSON stream.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def bind_request_context(**kwargs: Any) -> None:
    """Bind values to contextvars so all log lines in this task include them."""
    bind_contextvars(**kwargs)


def clear_request_context() -> None:
    clear_contextvars()


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name) if name else structlog.get_logger()
