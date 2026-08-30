"""Compute per-band normalisation statistics over the TRAINING SPLIT ONLY.

CLAUDE.md §7: preprocessing that learns parameters is fitted on training data alone. This
script is the only sanctioned producer of ``configs/norm_stats.yaml``.

It refuses to run on any split other than ``train``, and records ``split_hash`` and
``n_samples`` so a leakage test can prove that validation data did not influence the result.

Statistics are accumulated in a single streaming pass (Welford-style sums), so the full
training split never needs to fit in memory.

**Requires imagery**, which is the 117.69 GB tier deferred to the cloud instance
(PROJECT_STATUS.md standing decision). Until that lands this script has no data to run on;
it fails loudly rather than emitting fabricated statistics.

Usage::

    uv run python scripts/data/compute_norm_stats.py --imagery-root <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
import yaml

from satquery.preprocessing.bands import CHANNEL_ORDER, S1_BANDS
from satquery.preprocessing.sensors import linear_to_db
from satquery.utils.paths import project_root

ALLOWED_SPLIT = "train"


def split_hash(patch_ids: list[str]) -> str:
    """Stable hash of the exact sample list the statistics were computed over."""
    digest = hashlib.sha256()
    for pid in sorted(patch_ids):
        digest.update(pid.encode("utf-8"))
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    """Compute and write normalisation statistics.

    Args:
        argv: Command-line arguments after the script name.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--imagery-root", type=Path, required=True,
                        help="directory of per-patch S1/S2 rasters")
    parser.add_argument("--split", default=ALLOWED_SPLIT,
                        help=f"must be '{ALLOWED_SPLIT}' (CLAUDE.md §7)")
    parser.add_argument("--limit", type=int, default=0, help="stop after N patches (0 = all)")
    parser.add_argument("--out", type=Path, default=project_root() / "configs/norm_stats.yaml")
    args = parser.parse_args(argv)

    if args.split != ALLOWED_SPLIT:
        print(
            f"REFUSING: statistics may only be computed over '{ALLOWED_SPLIT}'. "
            f"Fitting them on '{args.split}' leaks across the split (CLAUDE.md §7).",
            file=sys.stderr,
        )
        return 2

    if not args.imagery_root.is_dir():
        print(f"imagery root not found: {args.imagery_root}", file=sys.stderr)
        print(
            "Imagery is the 117.69 GB deferred tier — see the standing storage decision in "
            "PROJECT_STATUS.md. This script emits nothing without it.",
            file=sys.stderr,
        )
        return 1

    # Streaming accumulators, one per frozen channel.
    n = dict.fromkeys(CHANNEL_ORDER, 0)
    total = dict.fromkeys(CHANNEL_ORDER, 0.0)
    total_sq = dict.fromkeys(CHANNEL_ORDER, 0.0)
    seen: list[str] = []

    files = sorted(args.imagery_root.rglob("*.tif"))
    if args.limit:
        files = files[: args.limit]
    if not files:
        print(f"no rasters found under {args.imagery_root}", file=sys.stderr)
        return 1

    for path in files:
        seen.append(path.stem)
        with rasterio.open(path) as ds:
            descriptions = list(ds.descriptions or [])
            for i in range(ds.count):
                name = descriptions[i] if i < len(descriptions) and descriptions[i] else None
                if name not in CHANNEL_ORDER:
                    continue
                arr = ds.read(i + 1).astype(np.float64)
                if name in S1_BANDS:
                    arr = linear_to_db(arr).values.astype(np.float64)
                finite = arr[np.isfinite(arr)]
                if finite.size == 0:
                    continue
                n[name] += int(finite.size)
                total[name] += float(finite.sum())
                total_sq[name] += float(np.square(finite).sum())

    bands = {}
    for name in CHANNEL_ORDER:
        if n[name] == 0:
            print(f"REFUSING: no pixels observed for band {name}", file=sys.stderr)
            return 1
        mean = total[name] / n[name]
        var = max(total_sq[name] / n[name] - mean * mean, 0.0)
        bands[name] = {"mean": round(mean, 6), "std": round(float(np.sqrt(var)), 6)}

    payload = {
        "bands": bands,
        "split": args.split,
        "split_hash": split_hash(seen),
        "n_samples": len(seen),
        "computed_at": datetime.now(UTC).isoformat(),
        "sar_units": "db",
        "note": (
            "Computed over the TRAINING SPLIT ONLY (CLAUDE.md §7). SAR statistics are in dB, "
            "after linear->dB conversion. Do not regenerate from any other split."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    print(f"wrote {args.out}  ({len(seen):,} patches, split={args.split})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
