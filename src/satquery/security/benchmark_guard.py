"""Benchmark-split quarantine guard.

CLAUDE.md §7: the benchmark evaluation split (1,082 image pairs / 15,029 annotations) is
sealed. It may be touched **once**, at final evaluation. "Enforce this in code — a loader
guard that raises unless ``ALLOW_BENCHMARK_EVAL=1`` is set."

Any loader that opens the benchmark split must call :func:`assert_benchmark_access_allowed`
first. Tuning on this split is the failure mode that produces a number which does not survive
the hidden set, so the guard denies by default and must be opened deliberately.
"""

from __future__ import annotations

import os

from satquery.exceptions import ContractViolationError

__all__ = ["BENCHMARK_GUARD_ENV", "assert_benchmark_access_allowed", "benchmark_access_allowed"]

BENCHMARK_GUARD_ENV = "ALLOW_BENCHMARK_EVAL"
_ALLOWED_VALUE = "1"


def benchmark_access_allowed(*, env: dict[str, str] | None = None) -> bool:
    """Whether benchmark-split access is currently permitted.

    Args:
        env: Environment mapping to consult. Defaults to :data:`os.environ`.

    Returns:
        True only if the guard variable is set to exactly ``"1"``.
    """
    source = env if env is not None else dict(os.environ)
    return source.get(BENCHMARK_GUARD_ENV, "") == _ALLOWED_VALUE


def assert_benchmark_access_allowed(
    *,
    caller: str,
    env: dict[str, str] | None = None,
) -> None:
    """Raise unless benchmark-split access has been explicitly enabled.

    Args:
        caller: Identifier of the code requesting access, recorded in the error context.
        env: Environment mapping to consult. Defaults to :data:`os.environ`.

    Raises:
        ContractViolationError: If the guard is not set to ``"1"``.
    """
    if not benchmark_access_allowed(env=env):
        raise ContractViolationError(
            "benchmark split is quarantined (CLAUDE.md §7); "
            f"set {BENCHMARK_GUARD_ENV}=1 only for the single final evaluation run",
            caller=caller,
            guard_env=BENCHMARK_GUARD_ENV,
        )
