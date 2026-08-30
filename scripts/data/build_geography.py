"""Extract and cache per-patch geography for the reBEN training split.

Splitting needs three independent location signals, and they are not equivalent:

- **country** — coarse administrative block, available for every patch.
- **1-degree grid cell** — from latitude/longitude.
- **tile + (row, col)** — parsed from the patch id, e.g. ``..._T33UUP_26_57`` is row 26,
  column 57 within tile T33UUP. This is the only signal that gives *exact* pixel-grid
  adjacency, and it is what makes it possible to test the real leakage claim rather than a
  proxy for it: two patches in the same tile differing by at most one in row and column are
  physically touching.

Latitude/longitude live in BigEarthNet.txt. Only ``train`` rows are read — the quarantined
``bench`` split is never touched (CLAUDE.md §7), enforced by the forensics loader.

Output: ``data/processed/geography_train.parquet``.
"""

from __future__ import annotations

import argparse
import re
import sys

import pandas as pd

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = "data/processed/geography_train.parquet"

#: ``..._T33UUP_26_57`` -> tile T33UUP, row 26, col 57.
PATCH_ID = re.compile(r"_(T\d{2}[A-Z]{3})_(\d+)_(\d+)$")


def main(argv: list[str]) -> int:
    """Build the geography table.

    Args:
        argv: Command-line arguments after the script name.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="train", choices=["train", "validation"])
    parser.add_argument("--row-groups", type=int, default=0,
                        help="limit row groups read (0 = all); for a fast trial")
    args = parser.parse_args(argv)

    root = project_root()
    md = pd.read_parquet(
        root / "data/raw/reben/metadata.parquet",
        columns=["patch_id", "split", "country"],
    )
    subset = md[md.split == args.split].copy()
    print(f"{args.split} patches: {len(subset):,}")

    parts = subset.patch_id.str.extract(PATCH_ID)
    parts.columns = ["tile", "row", "col"]
    unparsed = int(parts.tile.isna().sum())
    if unparsed:
        print(f"REFUSING: {unparsed:,} patch ids do not encode tile+row+col", file=sys.stderr)
        return 1
    subset["tile"] = parts.tile
    subset["row"] = parts.row.astype(int)
    subset["col"] = parts.col.astype(int)
    print(f"tiles: {subset.tile.nunique()}   "
          f"row {subset.row.min()}..{subset.row.max()}   "
          f"col {subset.col.min()}..{subset.col.max()}")

    groups = range(args.row_groups) if args.row_groups else None
    coords: dict[str, tuple[float, float]] = {}
    for frame in iter_annotations(
        ["patch_id", "latitude", "longitude"], splits=(args.split,), row_groups=groups
    ):
        for pid, lat, lon in zip(frame.patch_id, frame.latitude, frame.longitude, strict=True):
            if pid not in coords:
                coords[pid] = (float(lat), float(lon))
    print(f"lat/lon recovered for {len(coords):,} distinct patches")

    subset["lat"] = subset.patch_id.map(lambda p: coords.get(p, (None, None))[0])
    subset["lon"] = subset.patch_id.map(lambda p: coords.get(p, (None, None))[1])
    missing = int(subset.lat.isna().sum())
    print(f"patches WITHOUT lat/lon: {missing:,} ({100 * missing / len(subset):.2f}%)")
    if missing:
        print("  (these carry no BigEarthNet.txt annotation; they keep tile/row/col blocking)")

    out = root / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    subset.to_parquet(out, index=False)
    print(f"wrote {out}  ({len(subset):,} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
