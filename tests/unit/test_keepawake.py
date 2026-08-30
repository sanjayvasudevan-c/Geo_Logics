"""Sleep prevention holds for the duration of a block and is always released.

Added after the S2 extraction was killed at 38% by Modern Standby.
"""

from __future__ import annotations

import sys

import pytest

from satquery.utils.keepawake import keep_awake, sleep_prevention_available

pytestmark = pytest.mark.unit


class TestContract:
    def test_yields_a_bool(self) -> None:
        with keep_awake("test") as active:
            assert isinstance(active, bool)

    def test_reports_platform_support_honestly(self) -> None:
        """CLAUDE.md §5: report the real state, never assume it worked."""
        assert sleep_prevention_available() == (sys.platform == "win32")

    def test_releases_on_exception(self) -> None:
        """A crash inside the block must not leave the request asserted."""
        with pytest.raises(ValueError), keep_awake("test"):
            raise ValueError("boom")

    def test_is_reentrant_across_sequential_blocks(self) -> None:
        with keep_awake("first") as a:
            pass
        with keep_awake("second") as b:
            pass
        assert a == b

    def test_nested_blocks_do_not_error(self) -> None:
        with keep_awake("outer"), keep_awake("inner") as inner:
            assert isinstance(inner, bool)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only behaviour")
class TestWindows:
    def test_actually_activates_on_windows(self) -> None:
        with keep_awake("test") as active:
            assert active is True, "SetThreadExecutionState should succeed on Windows"


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows behaviour")
class TestOtherPlatforms:
    def test_is_a_reported_noop(self) -> None:
        with keep_awake("test") as active:
            assert active is False
