"""Environment capture returns a complete, non-empty record."""

from __future__ import annotations

import json

import pytest

from satquery.utils.environment import (
    TRACKED_PACKAGES,
    EnvironmentRecord,
    capture_environment,
    git_commit,
)

pytestmark = pytest.mark.unit


class TestCompleteness:
    def test_returns_a_record(self) -> None:
        assert isinstance(capture_environment(), EnvironmentRecord)

    def test_core_fields_are_populated(self) -> None:
        record = capture_environment()
        assert record.python_version.strip()
        assert record.python_implementation.strip()
        assert record.platform.strip()
        assert record.processor.strip()
        assert record.captured_at.strip()

    def test_no_core_field_is_none(self) -> None:
        record = capture_environment()
        for field in ("captured_at", "python_version", "python_implementation", "platform"):
            assert getattr(record, field) is not None, f"{field} is None"

    def test_timestamp_is_iso_utc(self) -> None:
        from datetime import datetime

        parsed = datetime.fromisoformat(capture_environment().captured_at)
        assert parsed.tzinfo is not None

    def test_every_tracked_package_is_reported(self) -> None:
        """Absence is recorded explicitly as None, never by omission."""
        packages = capture_environment().packages
        assert set(packages) == set(TRACKED_PACKAGES)

    def test_installed_packages_report_a_version(self) -> None:
        packages = capture_environment().packages
        for name in ("numpy", "pydantic", "pyyaml", "structlog"):
            assert packages[name] is not None, f"{name} should be installed"
            assert packages[name].strip()

    def test_gpu_block_is_always_present_and_explicit(self) -> None:
        """CLAUDE.md §5: report the real state, including 'no GPU'."""
        gpu = capture_environment().gpu
        assert "available" in gpu
        assert isinstance(gpu["available"], bool)
        assert "devices" in gpu
        if not gpu["available"]:
            assert gpu["reason"], "unavailability must state a reason"
        else:
            assert len(gpu["devices"]) >= 1

    def test_seed_is_recorded_when_supplied(self) -> None:
        assert capture_environment(seed=1337).seed == 1337

    def test_seed_is_none_when_not_supplied(self) -> None:
        assert capture_environment().seed is None


class TestGitCapture:
    def test_git_commit_returns_a_pair(self) -> None:
        sha, dirty = git_commit()
        assert (sha is None) or (isinstance(sha, str) and len(sha) == 40)
        assert dirty is None or isinstance(dirty, bool)

    def test_record_carries_the_commit(self) -> None:
        record = capture_environment()
        if record.git_commit is not None:
            assert len(record.git_commit) == 40
            assert record.git_dirty is not None


class TestSerialisation:
    def test_record_is_json_serialisable(self) -> None:
        payload = json.dumps(capture_environment(seed=7).to_dict(), default=str)
        assert json.loads(payload)["seed"] == 7

    def test_to_dict_is_non_empty_and_complete(self) -> None:
        record = capture_environment().to_dict()
        expected = {
            "captured_at", "python_version", "python_implementation", "platform",
            "processor", "packages", "git_commit", "git_dirty", "gpu", "seed",
        }
        assert expected <= set(record)

    def test_record_is_frozen(self) -> None:
        record = capture_environment()
        with pytest.raises((AttributeError, TypeError, ValueError)):
            record.seed = 1  # type: ignore[misc]
