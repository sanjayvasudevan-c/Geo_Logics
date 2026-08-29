"""Fetch the BigEarthNet.txt annotation parquet from Hugging Face.

~467 MB, CDLA-Permissive-1.0, not gated. Pinned to an exact repository revision so a later
upstream edit cannot silently change what we train and score against.

This file contains the quarantined benchmark split. Downloading it is fine; *reading* that
split requires ``ALLOW_BENCHMARK_EVAL=1`` and is enforced by
``satquery.security.benchmark_guard`` (CLAUDE.md §7).

Usage::

    uv run python scripts/data/fetch_bigearthnet_txt.py --dry-run
    uv run python scripts/data/fetch_bigearthnet_txt.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time

import yaml

from satquery.data.download import FileSpec, download_file
from satquery.utils.paths import configs_dir, project_root

MANIFEST = "datasets/bigearthnet_txt.yaml"
DEST = "data/raw/bigearthnet_txt"


def _load() -> tuple[list[FileSpec], dict[str, str]]:
    raw = yaml.safe_load((configs_dir() / MANIFEST).read_text(encoding="utf-8"))
    base = raw["base_url"]
    specs = [
        FileSpec(
            key=e["key"],
            url=f"{base}/{e['key']}",
            size_bytes=e["size_bytes"],
            checksum=e["checksum"],
            algorithm=e.get("algorithm", "sha256"),
            tier=e.get("tier", "core"),
            purpose=" ".join(e.get("purpose", "").split()),
        )
        for e in raw["files"].values()
    ]
    meta = {
        "repo": raw["repo"],
        "licence": raw["licence"],
        "revision": raw["revision"],
    }
    return specs, meta


def main(argv: list[str]) -> int:
    """Fetch the annotation parquet.

    Args:
        argv: Command-line arguments after the script name.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report the plan, fetch nothing")
    args = parser.parse_args(argv)

    specs, meta = _load()
    dest = project_root() / DEST
    total = sum(s.size_bytes for s in specs)
    free = shutil.disk_usage(project_root()).free

    print(f"BigEarthNet.txt — {meta['repo']}, licence {meta['licence']}")
    print(f"revision    : {meta['revision']}")
    print(f"destination : {dest}")
    print(f"size        : {total / 1e6:.2f} MB")
    print(f"free disk   : {free / 1e9:.2f} GB")
    print()

    if total > free * 0.5:
        print(f"REFUSING: {total / 1e9:.2f} GB exceeds half of {free / 1e9:.2f} GB free.")
        return 1

    if args.dry_run:
        print("dry run — nothing fetched")
        return 0

    for spec in specs:
        started = time.monotonic()
        last = [0.0]

        def progress(done: int, size: int, _l: list[float] = last) -> None:
            now = time.monotonic()
            if now - _l[0] < 3.0 and done < size:
                return
            _l[0] = now
            print(f"    {done / 1e6:8.1f} / {size / 1e6:8.1f} MB", flush=True)

        print(f"  fetching {spec.key} ...")
        path = download_file(spec, dest, on_progress=progress)
        print(
            f"  OK {path.name}  {path.stat().st_size:,} B  "
            f"{spec.algorithm} verified  {time.monotonic() - started:.1f}s"
        )

    print(f"\ndone. verified in {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
