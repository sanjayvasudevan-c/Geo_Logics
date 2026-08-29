"""Fetch reBEN's core (non-imagery) files from Zenodo.

Downloads only the ``tier: core`` entries in ``configs/datasets/reben.yaml`` — the CORINE
reference maps and the metadata parquets, ~287 MB total. The 117.69 GB of imagery is
``tier: deferred`` and is never fetched by this script; see the standing storage decision in
PROJECT_STATUS.md.

Usage::

    uv run python scripts/data/fetch_reben.py --dry-run
    uv run python scripts/data/fetch_reben.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time

import yaml

from satquery.data.download import FileSpec, download_file
from satquery.utils.paths import configs_dir, project_root

MANIFEST = "datasets/reben.yaml"
DEST = "data/raw/reben"


def _load_specs(tier: str) -> tuple[list[FileSpec], str]:
    raw = yaml.safe_load((configs_dir() / MANIFEST).read_text(encoding="utf-8"))
    base = raw["base_url"]
    specs = [
        FileSpec(
            key=entry["key"],
            url=f"{base}/{entry['key']}/content",
            size_bytes=entry["size_bytes"],
            checksum=entry["md5"],
            algorithm="md5",
            tier=entry.get("tier", "core"),
            purpose=" ".join(entry.get("purpose", "").split()),
        )
        for entry in raw["files"].values()
        if entry.get("tier", "core") == tier
    ]
    return specs, raw["licence"]


def main(argv: list[str]) -> int:
    """Fetch the core reBEN files.

    Args:
        argv: Command-line arguments after the script name.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", default="core", choices=["core", "deferred"])
    parser.add_argument("--dry-run", action="store_true", help="report the plan, fetch nothing")
    args = parser.parse_args(argv)

    specs, licence = _load_specs(args.tier)
    dest = project_root() / DEST
    total = sum(s.size_bytes for s in specs)
    free = shutil.disk_usage(project_root()).free

    print(f"reBEN — Zenodo, licence {licence}")
    print(f"tier '{args.tier}': {len(specs)} file(s), {total / 1e9:.2f} GB")
    print(f"destination : {dest}")
    print(f"free disk   : {free / 1e9:.2f} GB")
    print()
    for spec in specs:
        print(f"  {spec.key:56s} {spec.size_bytes / 1e6:9.2f} MB")
    print()

    if args.tier == "deferred":
        print("REFUSING: 'deferred' tier is the 117.69 GB imagery. It is not fetched locally.")
        print("See the standing storage decision in PROJECT_STATUS.md.")
        return 1

    if total > free * 0.5:
        print(f"REFUSING: {total / 1e9:.2f} GB is more than half of {free / 1e9:.2f} GB free.")
        return 1

    if args.dry_run:
        print("dry run — nothing fetched")
        return 0

    for spec in specs:
        started = time.monotonic()
        last = [0.0]

        def progress(done: int, size: int, _s: object = spec, _l: list[float] = last) -> None:
            now = time.monotonic()
            if now - _l[0] < 2.0 and done < size:
                return
            _l[0] = now
            pct = 100.0 * done / size if size else 0.0
            print(f"    {done / 1e6:9.1f} / {size / 1e6:9.1f} MB  ({pct:5.1f}%)", flush=True)

        print(f"  fetching {spec.key} ...")
        path = download_file(spec, dest, on_progress=progress)
        elapsed = time.monotonic() - started
        print(f"  OK {path.name}  {path.stat().st_size:,} B  md5 verified  {elapsed:.1f}s")
        print()

    print(f"done. {len(specs)} file(s) verified in {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
