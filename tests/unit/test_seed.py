"""Seeding is deterministic: same seed produces the same draws across all three libraries."""

from __future__ import annotations

import random

import numpy as np
import pytest

from satquery.utils.seed import SeedReport, set_global_seed

pytestmark = pytest.mark.unit

SEED = 1337
OTHER_SEED = 2024


def _draw_all() -> tuple[float, float, list[float]]:
    """Draw one sample from each seeded library."""
    import torch

    py_draw = random.random()
    np_draw = float(np.random.rand())
    torch_draw = torch.rand(4).tolist()
    return py_draw, np_draw, torch_draw


class TestDeterminism:
    def test_same_seed_reproduces_all_three_libraries(self) -> None:
        set_global_seed(SEED)
        first = _draw_all()

        set_global_seed(SEED)
        second = _draw_all()

        assert first[0] == second[0], "random module diverged"
        assert first[1] == second[1], "numpy diverged"
        assert first[2] == second[2], "torch diverged"

    def test_different_seeds_diverge(self) -> None:
        """Guards against a seeding function that silently does nothing."""
        set_global_seed(SEED)
        first = _draw_all()

        set_global_seed(OTHER_SEED)
        second = _draw_all()

        assert first != second

    def test_repeated_sequences_match_beyond_the_first_draw(self) -> None:
        set_global_seed(SEED)
        first = [_draw_all() for _ in range(3)]

        set_global_seed(SEED)
        second = [_draw_all() for _ in range(3)]

        assert first == second

    def test_numpy_generator_arrays_match(self) -> None:
        set_global_seed(SEED)
        first = np.random.randn(16).tolist()

        set_global_seed(SEED)
        second = np.random.randn(16).tolist()

        assert first == second


class TestSeedReport:
    def test_report_names_the_libraries_actually_seeded(self) -> None:
        report = set_global_seed(SEED)
        assert isinstance(report, SeedReport)
        assert report.seed == SEED
        assert "random" in report.libraries
        assert "numpy" in report.libraries
        assert "torch" in report.libraries

    def test_report_does_not_claim_cuda_when_unavailable(self) -> None:
        """CLAUDE.md §5: report what happened, never what should have happened."""
        import torch

        report = set_global_seed(SEED)
        assert report.cuda_available == torch.cuda.is_available()
        if not report.cuda_available:
            assert "torch.cuda" not in report.libraries

    def test_deterministic_flag_is_recorded(self) -> None:
        assert set_global_seed(SEED, deterministic=True).deterministic_algorithms is True
        assert set_global_seed(SEED, deterministic=False).deterministic_algorithms is False

    def test_report_is_frozen(self) -> None:
        report = set_global_seed(SEED)
        with pytest.raises((AttributeError, TypeError, ValueError)):
            report.seed = 1  # type: ignore[misc]


class TestValidation:
    @pytest.mark.parametrize("bad_seed", [-1, 2**32, 2**40])
    def test_out_of_range_seed_rejected(self, bad_seed: int) -> None:
        with pytest.raises(ValueError, match="seed must be in"):
            set_global_seed(bad_seed)

    @pytest.mark.parametrize("edge_seed", [0, 2**32 - 1])
    def test_boundary_seeds_accepted(self, edge_seed: int) -> None:
        assert set_global_seed(edge_seed).seed == edge_seed
