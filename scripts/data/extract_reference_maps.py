"""Extract reBEN CORINE Level-3 reference maps from the Zenodo archive.

Extracts **all** 480,038 reference maps, not a stratified subset. That decision is evidence-based
and is recorded in ``docs/datasets/reBEN_dev_subset.md``:

- Measured cost is 1,034.8 B logical / 3,670 B allocated per map (NTFS 4 KiB clusters), so the
  full set is ~0.50 GB logical and ~1.76 GB on disk — well inside the local budget.
- A rare-class probe over 30,000 patches found 6 CLC L3 classes present in under 0.1% of
  patches, the rarest in 3 of 30,000. Subsetting to ~20,000 patches would leave that class
  around 2 patches, which is unusable for a per-class oracle measurement. Taking 100% removes
  the starvation risk entirely.

Output is sharded by Sentinel-2 tile id (54 tiles). A single flat directory of 480k entries is
slow on NTFS; sharding by tile keeps directory sizes workable and is semantically meaningful,
since the tile is also the geographic blocking unit for splits.

Usage::

    uv run python scripts/data/extract_reference_maps.py --limit 5000   # trial
    uv run python scripts/data/extract_reference_maps.py                # full
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import sys
import tarfile
import time
from pathlib import Path

import zstandard

from satquery.utils.paths import project_root

ARCHIVE = "data/raw/reben/Reference_Maps.tar.zst"
OUT_DIR = "data/interim/reben/reference_maps"
MANIFEST = "data/interim/reben/reference_maps_manifest.json"

#: Tile id embedded in every patch id, e.g. ..._T33UUP_26_57.
_TILE = re.compile(r"_(T\d{2}[A-Z]{3})_")

#: Recorded for provenance. Extraction is exhaustive, so no sampling RNG is used; the seed is
#: carried so downstream stratified splits built from this store can be tied back to it.
SEED = 1337


def _patch_id(member_name: str) -> str:
    return Path(member_name).name.replace("_reference_map.tif", "")


def main(argv: list[str]) -> int:
    """Extract the reference maps.

    Args:
        argv: Command-line arguments after the script name.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="stop after N maps (0 = all)")
    parser.add_argument("--force", action="store_true", help="re-extract even if complete")
    args = parser.parse_args(argv)

    root = project_root()
    archive = root / ARCHIVE
    out = root / OUT_DIR
    manifest_path = root / MANIFEST

    if not archive.is_file():
        print(f"missing archive: {archive}", file=sys.stderr)
        print("run: uv run python scripts/data/fetch_reben.py", file=sys.stderr)
        return 1

    if manifest_path.is_file() and not args.force:
        prior = json.loads(manifest_path.read_text(encoding="utf-8"))
        print(f"already extracted: {prior['count']:,} maps. Use --force to redo.")
        return 0

    out.mkdir(parents=True, exist_ok=True)
    free_before = shutil.disk_usage(root).free
    started = time.monotonic()

    count = 0
    logical = 0
    per_tile: collections.Counter[str] = collections.Counter()
    no_tile: list[str] = []

    dctx = zstandard.ZstdDecompressor()
    with (
        archive.open("rb") as fh,
        dctx.stream_reader(fh) as reader,
        tarfile.open(fileobj=reader, mode="r|") as tar,
    ):
        for member in tar:
            if not member.isfile() or not member.name.endswith(".tif"):
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            data = handle.read()

            pid = _patch_id(member.name)
            match = _TILE.search(pid)
            tile = match.group(1) if match else "UNKNOWN"
            if match is None and len(no_tile) < 10:
                no_tile.append(pid)

            shard = out / tile
            shard.mkdir(exist_ok=True)
            (shard / f"{pid}.tif").write_bytes(data)

            logical += len(data)
            per_tile[tile] += 1
            count += 1

            if count % 25000 == 0:
                rate = count / (time.monotonic() - started)
                print(f"  {count:,} maps  ({rate:,.0f}/s)", flush=True)
            if args.limit and count >= args.limit:
                break

    elapsed = time.monotonic() - started
    allocated = free_before - shutil.disk_usage(root).free

    manifest = {
        "source_archive": ARCHIVE,
        "seed": SEED,
        "selection": "exhaustive — all reference maps in the archive, no subsetting",
        "selection_rationale": (
            "Measured 3,670 B/map allocated, so the full set costs ~1.76 GB on disk, inside "
            "budget. A 30,000-patch probe found 6 CLC L3 classes in <0.1% of patches (rarest "
            "3/30,000); a ~20,000-patch subset would starve them to ~2 patches each."
        ),
        "count": count,
        "logical_bytes": logical,
        "allocated_bytes": allocated,
        "bytes_per_map_logical": round(logical / count, 1) if count else 0,
        "bytes_per_map_allocated": round(allocated / count, 1) if count else 0,
        "elapsed_seconds": round(elapsed, 1),
        "shard_by": "sentinel2_tile_id",
        "shards": len(per_tile),
        "patches_per_shard": dict(sorted(per_tile.items())),
        "patch_ids_without_tile": no_tile,
        "limit_applied": args.limit or None,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print()
    print(f"extracted : {count:,} maps into {len(per_tile)} tile shards")
    print(f"logical   : {logical / 1e9:.2f} GB")
    print(f"allocated : {allocated / 1e9:.2f} GB")
    print(f"elapsed   : {elapsed / 60:.1f} min")
    print(f"manifest  : {manifest_path}")
    if no_tile:
        print(f"WARNING: {len(no_tile)} patch ids had no parsable tile id, e.g. {no_tile[:3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
