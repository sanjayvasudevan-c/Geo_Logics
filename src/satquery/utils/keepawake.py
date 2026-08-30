"""Prevent the machine sleeping through a long-running job.

Added at S2 after a real incident: the reference-map extraction was killed at 38% because the
machine entered Modern Standby. The active power scheme sleeps after 10 minutes plugged in and
5 on battery, and a background extraction generates no input activity, so any run longer than
that window dies.

The fix is deliberately **process-scoped**, not a settings change. ``SetThreadExecutionState``
asserts a power request for the lifetime of the calling process and is released automatically
on exit — including on a crash, since Windows drops the request when the thread ends. Editing
the user's power scheme would be persistent, invasive, and easy to leave behind.

Non-Windows platforms are a no-op that reports ``False`` rather than pretending to have worked.

Usage::

    with keep_awake("extracting reference maps") as active:
        if not active:
            log.warning("sleep prevention unavailable; a long run may be interrupted")
        ...
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Iterator
from contextlib import contextmanager

__all__ = ["keep_awake", "sleep_prevention_available"]

#: Keep the flags in force until explicitly cleared, rather than for one call.
ES_CONTINUOUS = 0x80000000
#: Reset the system idle timer: forbids the transition to sleep / Modern Standby.
ES_SYSTEM_REQUIRED = 0x00000001


def sleep_prevention_available() -> bool:
    """Whether this platform supports process-scoped sleep prevention."""
    return sys.platform == "win32"


@contextmanager
def keep_awake(reason: str) -> Iterator[bool]:
    """Hold off system sleep for the duration of the block.

    Args:
        reason: Human-readable description of the work. Recorded by the caller in logs; Windows
            does not surface it for this API, but it keeps call sites self-documenting.

    Yields:
        True if sleep prevention is actually in force, False if it could not be established.
        Callers should treat False as "this run may be interrupted", not as a failure.
    """
    if not sleep_prevention_available():
        yield False
        return

    try:
        kernel32 = ctypes.windll.kernel32
    except (AttributeError, OSError):
        yield False
        return

    # Returns the previous state, or 0 on failure.
    previous = kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    active = previous != 0
    try:
        yield bool(active)
    finally:
        if active:
            # Release the request. Windows also drops it automatically if the process dies.
            kernel32.SetThreadExecutionState(ES_CONTINUOUS)
