"""Forensic loaders cannot return quarantined rows (CLAUDE.md §7)."""

from __future__ import annotations

import pandas as pd
import pytest

from satquery.evaluation.forensics import (
    BENCH_SPLIT,
    FORENSIC_SPLITS,
    assert_no_bench,
    iter_annotations,
)
from satquery.exceptions import ContractViolationError

pytestmark = pytest.mark.unit


class TestSplitPolicy:
    def test_bench_is_not_a_forensic_split(self) -> None:
        assert BENCH_SPLIT not in FORENSIC_SPLITS

    def test_forensic_splits_are_train_and_validation(self) -> None:
        assert set(FORENSIC_SPLITS) == {"train", "validation"}

    def test_requesting_bench_is_refused(self) -> None:
        with pytest.raises(ContractViolationError) as info:
            next(iter_annotations(["output"], splits=("train", BENCH_SPLIT)))
        assert "quarantined" in info.value.message

    def test_requesting_only_bench_is_refused(self) -> None:
        with pytest.raises(ContractViolationError):
            next(iter_annotations(["output"], splits=(BENCH_SPLIT,)))


class TestAssertNoBench:
    def test_clean_frame_passes(self) -> None:
        frame = pd.DataFrame({"split": ["train", "validation"], "output": ["yes", "no"]})
        assert_no_bench(frame, caller="test")

    def test_contaminated_frame_raises(self) -> None:
        frame = pd.DataFrame({"split": ["train", BENCH_SPLIT], "output": ["yes", "no"]})
        with pytest.raises(ContractViolationError) as info:
            assert_no_bench(frame, caller="test")
        assert info.value.context["leaked_rows"] == 1

    def test_reports_the_leak_count(self) -> None:
        frame = pd.DataFrame({"split": [BENCH_SPLIT] * 3 + ["train"]})
        with pytest.raises(ContractViolationError) as info:
            assert_no_bench(frame, caller="test")
        assert info.value.context["leaked_rows"] == 3

    def test_frame_without_split_column_passes(self) -> None:
        assert_no_bench(pd.DataFrame({"output": ["yes"]}), caller="test")
