"""Cross-platform task runner — the Makefile's equivalent for machines without GNU make.

``make`` is not installed on every developer machine (notably plain Windows). The Makefile
remains the canonical target list; this script runs the same commands through ``uv`` so the
targets are usable everywhere.

Usage::

    uv run python scripts/tasks.py test
    uv run python scripts/tasks.py check
    uv run python scripts/tasks.py            # lists the targets
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TASKS: dict[str, tuple[tuple[str, ...], ...]] = {
    "setup": (("uv", "sync", "--extra", "dev"),),
    "lint": (("uv", "run", "ruff", "check", "src", "tests", "scripts"),),
    "typecheck": (("uv", "run", "mypy"),),
    "test": (("uv", "run", "pytest"),),
    "test-unit": (("uv", "run", "pytest", "-m", "unit"),),
    "test-integration": (("uv", "run", "pytest", "-m", "integration"),),
    "coverage": (("uv", "run", "pytest", "--cov", "--cov-report=term-missing"),),
    "check": (
        ("uv", "run", "ruff", "check", "src", "tests", "scripts"),
        ("uv", "run", "mypy"),
        ("uv", "run", "pytest"),
    ),
    # Scoped to named caches only. CLAUDE.md §9 forbids sweeping a temp root, and
    # scripts/cleanup.py refuses to. Dry run by default; pass --apply to delete.
    "cleanup": (("uv", "run", "python", "scripts/cleanup.py"),),
}

DESCRIPTIONS = {
    "setup": "install the pinned environment",
    "lint": "ruff check on src/ and tests/",
    "typecheck": "mypy --strict on src/satquery",
    "test": "full pytest run",
    "test-unit": "pytest -m unit",
    "test-integration": "pytest -m integration",
    "coverage": "pytest with a coverage report",
    "check": "lint + typecheck + test",
}


def _usage() -> int:
    print("Targets:")
    for name in TASKS:
        print(f"  {name:<18} {DESCRIPTIONS.get(name, '')}")
    print("\n`make reproduce` has no equivalent here: it is not implemented as of Stage S1.")
    return 0


def main(argv: list[str]) -> int:
    """Run the named target.

    Args:
        argv: Command-line arguments after the script name.

    Returns:
        Process exit code. Non-zero on the first failing command.
    """
    if not argv:
        return _usage()

    target = argv[0]
    if target not in TASKS:
        print(f"unknown target: {target}\n", file=sys.stderr)
        _usage()
        return 2

    for command in TASKS[target]:
        print(f"$ {' '.join(command)}", flush=True)
        completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
