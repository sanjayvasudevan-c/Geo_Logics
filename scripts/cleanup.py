"""Safe disk cleanup — scoped to named caches, never a temp root.

CLAUDE.md §9 forbids blanket deletion of a temp root. This script is the only sanctioned
cleanup path, and it enforces two rules:

1. **Allow-list only.** Nothing is deleted unless its directory appears in :data:`CACHE_TARGETS`.
   There is no "sweep everything under TEMP" mode, because that is how in-flight work gets
   destroyed.
2. **The harness's own state is protected.** ``%TEMP%/claude/**`` holds Claude Code task output.
   A sweep that removes it deletes the output of the very command doing the sweeping. Any target
   resolving inside that tree is refused by :func:`_is_protected`.

Both rules were added after a real incident: an ad-hoc ``%TEMP%`` sweep during S2 deleted a
running command's output file mid-execution.

Usage::

    uv run python scripts/cleanup.py --dry-run     # report only, delete nothing (default)
    uv run python scripts/cleanup.py --apply       # actually delete
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

__all__ = ["CACHE_TARGETS", "PROTECTED_SUBTREES", "main"]

#: Directories that may be deleted. Every entry must be a specific, regenerable cache — never
#: a temp root, never a directory holding user data. Adding an entry is a deliberate decision.
CACHE_TARGETS: tuple[tuple[str, str], ...] = (
    ("pip cache", "{LOCALAPPDATA}/pip/cache"),
    ("ruff cache", "{PROJECT}/.ruff_cache"),
    ("mypy cache", "{PROJECT}/.mypy_cache"),
    ("pytest cache", "{PROJECT}/.pytest_cache"),
    ("coverage html", "{PROJECT}/htmlcov"),
)

#: Subtrees that must never be touched, whatever a target resolves to.
PROTECTED_SUBTREES: tuple[str, ...] = (
    "{TEMP}/claude",
)

#: Temp roots. Named here only so they can be REFUSED, never so they can be swept.
_TEMP_ROOT_KEYS = ("TEMP", "TMP", "TMPDIR")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _expand(template: str) -> Path | None:
    """Expand a target template, or return None if its environment variable is unset."""
    mapping = {
        "PROJECT": str(_project_root()),
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
        "TEMP": os.environ.get("TEMP") or os.environ.get("TMPDIR") or "",
    }
    try:
        expanded = template.format(**mapping)
    except KeyError:
        return None
    if any(part == "" for part in (mapping[k] for k in mapping if "{" + k + "}" in template)):
        return None
    return Path(expanded)


def _protected_paths() -> list[Path]:
    paths = []
    for template in PROTECTED_SUBTREES:
        resolved = _expand(template)
        if resolved is not None:
            paths.append(resolved.resolve(strict=False))
    return paths


def _temp_roots() -> list[Path]:
    roots = []
    for key in _TEMP_ROOT_KEYS:
        value = os.environ.get(key)
        if value:
            roots.append(Path(value).resolve(strict=False))
    return roots


def _is_protected(path: Path) -> str | None:
    """Return a refusal reason if ``path`` must not be deleted, else None."""
    resolved = path.resolve(strict=False)

    for root in _temp_roots():
        if resolved == root:
            return f"refuses to delete a temp root ({root})"

    for protected in _protected_paths():
        if resolved == protected or protected in resolved.parents or resolved in protected.parents:
            return f"overlaps protected subtree ({protected})"

    if resolved == Path(resolved.anchor):
        return "refuses to delete a filesystem root"

    return None


def _size_bytes(path: Path) -> int:
    total = 0
    for entry in path.rglob("*"):
        try:
            if entry.is_file() and not entry.is_symlink():
                total += entry.stat().st_size
        except OSError:
            continue
    return total


def _free_bytes() -> int:
    return shutil.disk_usage(_project_root()).free


def _plan() -> Iterator[tuple[str, Path, int, str | None]]:
    for label, template in CACHE_TARGETS:
        path = _expand(template)
        if path is None or not path.exists():
            continue
        yield label, path, _size_bytes(path), _is_protected(path)


def main(argv: list[str]) -> int:
    """Report or apply the scoped cleanup.

    Args:
        argv: Command-line arguments after the script name.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually delete (default: dry run)")
    args = parser.parse_args(argv)

    before = _free_bytes()
    print(f"free before : {before / 1e9:6.2f} GB")
    print(f"protected   : {', '.join(str(p) for p in _protected_paths()) or '(none resolved)'}")
    print()

    reclaimable = 0
    for label, path, size, refusal in _plan():
        if refusal is not None:
            print(f"  SKIP  {label:16s} {size / 1e9:7.2f} GB  — {refusal}")
            continue
        reclaimable += size
        if args.apply:
            shutil.rmtree(path, ignore_errors=True)
            print(f"  DEL   {label:16s} {size / 1e9:7.2f} GB  {path}")
        else:
            print(f"  would {label:16s} {size / 1e9:7.2f} GB  {path}")

    print()
    if args.apply:
        after = _free_bytes()
        print(f"reclaimed   : {(after - before) / 1e9:6.2f} GB")
        print(f"free now    : {after / 1e9:6.2f} GB")
    else:
        print(f"reclaimable : {reclaimable / 1e9:6.2f} GB  (dry run — nothing deleted)")
        print("re-run with --apply to delete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
