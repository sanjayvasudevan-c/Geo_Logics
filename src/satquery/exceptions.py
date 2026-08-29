"""Typed exception hierarchy for SatQuery.

CLAUDE.md §9 requires explicit exception types and forbids bare ``except:``. Every error
raised inside ``src/satquery`` derives from :class:`SatQueryError` and carries structured
context, so that a failure lands in the execution trace as data rather than as a string.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ConfigError",
    "ContractViolationError",
    "GeometryError",
    "InputValidationError",
    "ModelError",
    "RoutingError",
    "SatQueryError",
    "TaxonomyError",
]


class SatQueryError(Exception):
    """Base class for every SatQuery error.

    Carries an arbitrary structured ``context`` mapping alongside the message. The context
    is what gets written into the execution trace; the message is for humans.

    Args:
        message: Human-readable description of what went wrong.
        **context: Structured key/value detail describing the failure.
    """

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = dict(context)

    def __str__(self) -> str:
        if not self.context:
            return self.message
        rendered = ", ".join(f"{k}={v!r}" for k, v in sorted(self.context.items()))
        return f"{self.message} [{rendered}]"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.message!r}, context={self.context!r})"

    def to_dict(self) -> dict[str, Any]:
        """Render the error as a trace-ready record."""
        return {
            "error_type": type(self).__name__,
            "message": self.message,
            "context": dict(self.context),
        }


class ConfigError(SatQueryError):
    """Configuration is missing, malformed, or fails schema validation.

    Raised by :mod:`satquery.config` when a YAML file cannot be found or parsed, or when the
    merged configuration does not satisfy the Pydantic schema.
    """


class InputValidationError(SatQueryError):
    """V1 rejected an input.

    Band count, dtype, CRS, geotransform, shape, NoData, modality inference, or the pair
    co-registration check failed. This is the typed rejection V1 emits instead of a crash.
    """


class TaxonomyError(SatQueryError):
    """A taxonomy or hierarchy-aggregation operation is invalid.

    Unknown class id, unknown CLC level, or a missing entry in the L3(44) -> requested-level
    aggregation table. IMPLEMENTATION_MAP §5.3 ranks a wrong aggregation table as the second
    most damaging silent failure in the system, so it gets its own error type.
    """


class GeometryError(SatQueryError):
    """M2, the symbolic geometry engine, could not compute a quantity.

    Malformed class map, unfitted parameter (connectivity / MMU / opening kernel / dilation
    radius), or an operation requested on an empty or degenerate mask.
    """


class RoutingError(SatQueryError):
    """Q1/R1 could not parse a query or bind a valid tool plan.

    Unknown intent, an intent unsupported for the supplied input configuration, or a tool
    parameter outside its declared Pydantic bounds.
    """


class ModelError(SatQueryError):
    """A learned component (M1, M3-M10) failed to load or to run inference."""


class ContractViolationError(SatQueryError):
    """An architectural invariant was broken.

    This is the enforcement point for the rules in CLAUDE.md §2 that make the execution trace
    meaningful:

    - a scored number originated somewhere other than M2 (the number-flow rule);
    - a component consumed another component's natural language;
    - the scene cache was asked to serve a map produced by a different checkpoint;
    - the quarantined benchmark split was opened without ``ALLOW_BENCHMARK_EVAL=1``.

    A violation is a bug in the system, never bad user input.
    """
