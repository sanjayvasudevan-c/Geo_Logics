"""The benchmark split is quarantined by default (CLAUDE.md §7)."""

from __future__ import annotations

import pytest

from satquery.exceptions import ContractViolationError
from satquery.security.benchmark_guard import (
    BENCHMARK_GUARD_ENV,
    assert_benchmark_access_allowed,
    benchmark_access_allowed,
)

pytestmark = pytest.mark.unit


class TestDeniedByDefault:
    def test_empty_environment_denies(self) -> None:
        assert benchmark_access_allowed(env={}) is False

    def test_assert_raises_when_unset(self) -> None:
        with pytest.raises(ContractViolationError) as info:
            assert_benchmark_access_allowed(caller="test-loader", env={})
        assert info.value.context["caller"] == "test-loader"
        assert BENCHMARK_GUARD_ENV in str(info.value)

    @pytest.mark.parametrize("value", ["0", "", "true", "True", "yes", "2", " 1", "1 "])
    def test_only_exactly_one_opens_the_guard(self, value: str) -> None:
        """A near-miss value must not open the quarantine."""
        env = {BENCHMARK_GUARD_ENV: value}
        assert benchmark_access_allowed(env=env) is False
        with pytest.raises(ContractViolationError):
            assert_benchmark_access_allowed(caller="test-loader", env=env)


class TestExplicitlyEnabled:
    def test_value_one_allows(self) -> None:
        env = {BENCHMARK_GUARD_ENV: "1"}
        assert benchmark_access_allowed(env=env) is True
        assert_benchmark_access_allowed(caller="final-eval", env=env)


class TestProcessEnvironment:
    def test_reads_the_real_environment_when_none_supplied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(BENCHMARK_GUARD_ENV, raising=False)
        assert benchmark_access_allowed() is False

        monkeypatch.setenv(BENCHMARK_GUARD_ENV, "1")
        assert benchmark_access_allowed() is True
