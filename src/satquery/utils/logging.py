"""Structured JSON logging.

Stage 1 requirement 4: JSON logs carrying a run id, a stage name and a component name, with a
redaction filter in front of every field (see :mod:`satquery.utils.redaction`).

Logging is configured once per process via :func:`configure_logging`; components obtain a
bound logger via :func:`get_logger`.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, TextIO

import structlog

from satquery.utils.paths import project_root
from satquery.utils.redaction import RedactionProcessor

__all__ = ["configure_logging", "get_logger"]


def configure_logging(
    *,
    run_id: str,
    stage: str,
    level: str = "INFO",
    stream: TextIO | None = None,
    log_file: Path | None = None,
    root: Path | None = None,
) -> None:
    """Configure process-wide structured logging.

    Every emitted record carries ``run_id``, ``stage``, ``timestamp``, ``level`` and
    ``logger``, is passed through the redaction filter, and is rendered as one JSON object
    per line.

    Args:
        run_id: Identifier for this run. Written into every record and used as the run
            registry directory name.
        stage: Stage name, e.g. ``"S1"``. Written into every record.
        level: Minimum level to emit.
        stream: Destination stream. Defaults to ``sys.stdout``.
        log_file: Optional file to additionally write records to.
        root: Project root for path redaction. Defaults to the detected project root.
    """
    destination = stream if stream is not None else sys.stdout
    resolved_root = root if root is not None else project_root()

    handlers: list[logging.Handler] = [logging.StreamHandler(destination)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper()),
        handlers=handlers,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Redaction runs last before rendering, so it also covers fields injected by the
            # processors above (exception text can carry absolute paths).
            RedactionProcessor(resolved_root),
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
        logger_factory=structlog.PrintLoggerFactory(file=destination),
        cache_logger_on_first_use=False,
    )

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id=run_id, stage=stage)


def get_logger(component: str, **initial_values: Any) -> structlog.BoundLogger:
    """Return a logger bound to a component name.

    Args:
        component: Component identifier, e.g. ``"M1"``, ``"V1"``, ``"AnswerAssembler"``.
        **initial_values: Extra fields bound to every record from this logger.

    Returns:
        A bound structlog logger.
    """
    logger: structlog.BoundLogger = structlog.get_logger().bind(
        component=component, **initial_values
    )
    return logger
