"""Read-only loaders for benchmark forensics (Stage S3).

Every loader here **excludes the quarantined ``bench`` split** before returning a single row to
the caller. CLAUDE.md §7 seals that split until final evaluation; S3 must derive the answer
grammar from ``train`` and ``validation`` only.

The exclusion is enforced structurally rather than by convention: :func:`iter_annotations`
filters inside the row-group loop, so a caller cannot forget to filter, and
:func:`assert_no_bench` re-checks the returned frame. A forensic statistic computed on sealed
data would silently invalidate every downstream gate.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import pandas as pd
import pyarrow.parquet as pq

from satquery.exceptions import ContractViolationError
from satquery.utils.paths import project_root

__all__ = [
    "ANNOTATIONS_PARQUET",
    "BENCH_SPLIT",
    "FORENSIC_SPLITS",
    "assert_no_bench",
    "iter_annotations",
    "load_annotations",
    "open_annotations",
]

ANNOTATIONS_PARQUET = "data/raw/bigearthnet_txt/BigEarthNet.txt.parquet"

#: The sealed split. Never returned by any loader in this module.
BENCH_SPLIT = "bench"

#: The splits S3 is permitted to read.
FORENSIC_SPLITS: tuple[str, ...] = ("train", "validation")


def open_annotations() -> pq.ParquetFile:
    """Open the annotation parquet.

    Returns:
        An open :class:`pyarrow.parquet.ParquetFile`.

    Raises:
        FileNotFoundError: If the parquet has not been downloaded.
    """
    path = project_root() / ANNOTATIONS_PARQUET
    if not path.is_file():
        raise FileNotFoundError(
            f"annotation parquet not found: {path}. "
            "Run: uv run python scripts/data/fetch_bigearthnet_txt.py"
        )
    return pq.ParquetFile(path)


def assert_no_bench(frame: pd.DataFrame, *, caller: str) -> None:
    """Raise if a frame contains any quarantined row.

    Args:
        frame: Frame to check. A frame without a ``split`` column passes trivially.
        caller: Identifier recorded in the error context.

    Raises:
        ContractViolationError: If any row belongs to the sealed split.
    """
    if "split" not in frame.columns:
        return
    leaked = int((frame["split"] == BENCH_SPLIT).sum())
    if leaked:
        raise ContractViolationError(
            "quarantined benchmark rows reached a forensic statistic (CLAUDE.md §7)",
            caller=caller,
            leaked_rows=leaked,
        )


def iter_annotations(
    columns: Sequence[str] | None = None,
    *,
    splits: Sequence[str] = FORENSIC_SPLITS,
    row_groups: Sequence[int] | None = None,
) -> Iterator[pd.DataFrame]:
    """Stream annotation row groups with the quarantined split removed.

    Args:
        columns: Columns to read. ``split`` is always read so filtering can occur, and is
            dropped from the yielded frame only if the caller did not ask for it.
        splits: Splits to keep. ``bench`` is rejected outright.
        row_groups: Specific row groups to read. Defaults to all.

    Yields:
        One frame per row group, containing only permitted splits. Empty groups are skipped.

    Raises:
        ContractViolationError: If ``splits`` names the sealed split.
    """
    if BENCH_SPLIT in splits:
        raise ContractViolationError(
            "forensics may not read the quarantined benchmark split (CLAUDE.md §7)",
            caller="iter_annotations",
            requested=list(splits),
        )

    handle = open_annotations()
    wanted = list(columns) if columns is not None else None
    read_cols = None
    if wanted is not None:
        read_cols = list(dict.fromkeys([*wanted, "split"]))

    indices = range(handle.metadata.num_row_groups) if row_groups is None else row_groups
    keep = set(splits)

    for index in indices:
        frame = handle.read_row_group(index, columns=read_cols).to_pandas()
        frame = frame[frame["split"].isin(keep)]
        if frame.empty:
            continue
        if wanted is not None and "split" not in wanted:
            frame = frame.drop(columns=["split"])
        assert_no_bench(frame, caller="iter_annotations")
        yield frame.reset_index(drop=True)


def load_annotations(
    columns: Sequence[str] | None = None,
    *,
    splits: Sequence[str] = FORENSIC_SPLITS,
    row_groups: Sequence[int] | None = None,
) -> pd.DataFrame:
    """Load permitted annotations into one frame.

    Args:
        columns: Columns to read.
        splits: Splits to keep.
        row_groups: Specific row groups. Defaults to all — note the full table is ~9.5M rows,
            so pass a subset when a sample suffices.

    Returns:
        A single concatenated frame, guaranteed free of quarantined rows.
    """
    chunks = list(iter_annotations(columns, splits=splits, row_groups=row_groups))
    if not chunks:
        return pd.DataFrame(columns=list(columns) if columns else None)
    frame = pd.concat(chunks, ignore_index=True)
    assert_no_bench(frame, caller="load_annotations")
    return frame
