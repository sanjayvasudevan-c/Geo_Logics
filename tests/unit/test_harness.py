"""Evaluation harness: strict-vs-attempted accounting and the bootstrap CI.

**Why this file exists.** A coverage audit at S9 found `satquery/evaluation/harness.py` at
**0% coverage** — and it is the module that computed *every* Gate 1 number: the strict and
attempted accuracies, the abstention accounting, and the confidence interval on each row of
`GATE1_oracle.md`. An off-by-one in the percentile index would have put a wrong interval on the
whole gate report with nothing to catch it. A module that produces gate numbers must not be the
least-tested module in the package.

All fixtures are SYNTHETIC (CLAUDE.md §7): outcomes are hand-built so the correct accuracy is
known by construction rather than by re-running the same arithmetic the code under test uses.
"""

from __future__ import annotations

import pytest

from satquery.evaluation.harness import Scored, bootstrap_ci, score_task

pytestmark = pytest.mark.unit


def _mk(patch: str, correct: bool, abstained: bool = False, reason: str = "") -> Scored:
    return Scored(patch_id=patch, task="t", predicted=None if abstained else "yes",
                  truth="yes", correct=correct, abstained=abstained, reason=reason)


class TestStrictVersusAttempted:
    """The two accuracies must not be conflated — they name different failures."""

    def test_no_abstentions_makes_them_equal(self) -> None:
        items = [_mk(f"p{i}", i < 8) for i in range(10)]
        s = score_task("t", items, resamples=50)
        assert s.strict_accuracy == 0.8
        assert s.attempted_accuracy == 0.8
        assert s.abstain_rate == 0.0

    def test_an_abstention_counts_as_WRONG_in_strict_accuracy(self) -> None:
        """8 correct, 2 abstained. Strict = 8/10; attempted = 8/8."""
        items = [_mk(f"p{i}", True) for i in range(8)]
        items += [_mk(f"p{i}", False, abstained=True, reason="declined") for i in (8, 9)]
        s = score_task("t", items, resamples=50)
        assert s.strict_accuracy == 0.8
        assert s.attempted_accuracy == 1.0
        assert s.abstain_rate == 0.2
        assert s.n_attempted == 8

    def test_an_abstention_is_never_credited_as_correct(self) -> None:
        items = [_mk("p", False, abstained=True) for _ in range(5)]
        s = score_task("t", items, resamples=50)
        assert s.strict_accuracy == 0.0
        assert s.n_correct == 0

    def test_all_abstained_yields_zero_not_a_crash(self) -> None:
        s = score_task("t", [_mk(f"p{i}", False, abstained=True) for i in range(4)],
                       resamples=50)
        assert s.attempted_accuracy == 0.0     # 0/0 is reported as 0, not NaN
        assert s.abstain_rate == 1.0

    def test_empty_input_is_all_zeros(self) -> None:
        s = score_task("t", [], resamples=10)
        assert (s.n, s.strict_accuracy, s.attempted_accuracy, s.abstain_rate) == (0, 0.0, 0.0, 0.0)

    def test_abstention_reasons_are_counted_and_ranked(self) -> None:
        items = [_mk("p", False, abstained=True, reason="no threshold") for _ in range(3)]
        items += [_mk("p", False, abstained=True, reason="no comparator")]
        s = score_task("t", items, resamples=10)
        assert s.abstain_reasons == {"no threshold": 3, "no comparator": 1}
        assert list(s.to_dict()["abstain_reasons"]) == ["no threshold", "no comparator"]


class TestBootstrapResamplesPatchesNotAnnotations:
    """IMPLEMENTATION_MAP §8.3: several questions share one image, so their outcomes are
    correlated. Resampling annotations independently would report intervals that are too
    narrow — an over-confident gate number."""

    def test_a_perfect_score_has_a_degenerate_interval(self) -> None:
        lo, hi = bootstrap_ci([_mk(f"p{i}", True) for i in range(50)], resamples=200)
        assert lo == hi == 1.0

    def test_a_zero_score_has_a_degenerate_interval(self) -> None:
        lo, hi = bootstrap_ci([_mk(f"p{i}", False) for i in range(50)], resamples=200)
        assert lo == hi == 0.0

    def test_the_interval_brackets_the_point_estimate(self) -> None:
        items = [_mk(f"p{i}", i % 2 == 0) for i in range(100)]
        lo, hi = bootstrap_ci(items, resamples=500)
        assert lo <= 0.5 <= hi

    def test_correlated_patches_give_a_WIDER_interval_than_independent_ones(self) -> None:
        """The property the patch-level resample exists to preserve.

        Same 100 outcomes, same 50/50 accuracy. In one case each patch carries 10 questions
        that agree with each other; in the other every question is its own patch. Clustering
        means fewer independent units, so the interval MUST be wider. If this ever reverses,
        the resample has silently gone back to annotation level and every gate CI is too tight.
        """
        clustered = [_mk(f"patch{i // 10}", i // 10 < 5) for i in range(100)]
        independent = [_mk(f"patch{i}", i < 50) for i in range(100)]
        c_lo, c_hi = bootstrap_ci(clustered, resamples=800)
        i_lo, i_hi = bootstrap_ci(independent, resamples=800)
        assert (c_hi - c_lo) > (i_hi - i_lo)

    def test_it_is_deterministic_for_a_fixed_seed(self) -> None:
        items = [_mk(f"p{i}", i % 3 == 0) for i in range(60)]
        assert bootstrap_ci(items, resamples=300, seed=7) == \
            bootstrap_ci(items, resamples=300, seed=7)

    def test_a_different_seed_is_still_a_valid_interval(self) -> None:
        items = [_mk(f"p{i}", i % 3 == 0) for i in range(60)]
        lo, hi = bootstrap_ci(items, resamples=300, seed=99)
        assert 0.0 <= lo <= hi <= 1.0

    def test_empty_input_returns_zeros_rather_than_raising(self) -> None:
        assert bootstrap_ci([], resamples=100) == (0.0, 0.0)

    def test_a_single_patch_does_not_crash(self) -> None:
        lo, hi = bootstrap_ci([_mk("only", True), _mk("only", False)], resamples=100)
        assert lo == hi == 0.5

    def test_the_interval_is_ordered_and_in_range(self) -> None:
        for frac in (0.1, 0.37, 0.9):
            n = 80
            items = [_mk(f"p{i}", i < int(frac * n)) for i in range(n)]
            lo, hi = bootstrap_ci(items, resamples=400)
            assert 0.0 <= lo <= hi <= 1.0


class TestReportedDict:
    def test_to_dict_carries_both_accuracies_and_the_interval(self) -> None:
        items = [_mk(f"p{i}", True) for i in range(9)] + [
            _mk("p9", False, abstained=True, reason="declined")]
        d = score_task("t", items, resamples=100).to_dict()
        assert d["n"] == 10 and d["n_attempted"] == 9 and d["n_abstained"] == 1
        assert d["strict_accuracy"] == 0.9
        assert d["attempted_accuracy"] == 1.0
        assert d["ci95_low"] <= d["strict_accuracy"] <= d["ci95_high"]

    def test_reasons_are_capped_so_a_report_row_cannot_explode(self) -> None:
        items = [_mk("p", False, abstained=True, reason=f"reason {i}") for i in range(30)]
        assert len(score_task("t", items, resamples=10).to_dict()["abstain_reasons"]) <= 8
