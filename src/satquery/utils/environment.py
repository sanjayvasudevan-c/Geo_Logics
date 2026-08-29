"""Environment capture for reproducibility.

CLAUDE.md §8: every metric report must record the model, dataset, split sizes, preprocessing,
hyperparameters, seed, metrics and timings; every saved model must record its git commit. This
module captures the machine-side half of that record.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from typing import Any

__all__ = ["EnvironmentRecord", "capture_environment", "git_commit"]

#: Packages whose versions materially affect results and are therefore always recorded.
TRACKED_PACKAGES: tuple[str, ...] = (
    "numpy",
    "scipy",
    "scikit-image",
    "scikit-learn",
    "rasterio",
    "torch",
    "torchvision",
    "lightgbm",
    "pydantic",
    "pandas",
    "pyarrow",
    "pyyaml",
    "structlog",
)


@dataclass(frozen=True)
class EnvironmentRecord:
    """A complete snapshot of the execution environment.

    Attributes:
        captured_at: UTC ISO-8601 timestamp.
        python_version: Full interpreter version string.
        python_implementation: e.g. ``CPython``.
        platform: Human-readable OS/architecture description.
        processor: Processor identifier as reported by the OS.
        packages: Mapping of tracked package name to installed version. A package that is not
            installed maps to ``None`` rather than being omitted, so the record is explicit.
        git_commit: Current commit SHA, or ``None`` outside a git work tree.
        git_dirty: Whether the work tree has uncommitted changes. ``None`` if unknown.
        gpu: GPU description. Always present; reports unavailability explicitly.
        seed: The global seed in force, when the caller supplies one.
    """

    captured_at: str
    python_version: str
    python_implementation: str
    platform: str
    processor: str
    packages: dict[str, str | None] = field(default_factory=dict)
    git_commit: str | None = None
    git_dirty: bool | None = None
    gpu: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Render as a plain dictionary for JSON serialisation."""
        return asdict(self)


def _run_git(*args: str) -> str | None:
    """Run a git command, returning stripped stdout or ``None`` if git is unavailable."""
    try:
        completed = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def git_commit() -> tuple[str | None, bool | None]:
    """Return ``(commit_sha, is_dirty)`` for the current work tree.

    Returns:
        The commit SHA and whether the tree has uncommitted changes. Both are ``None`` when
        git is unavailable or the directory is not a work tree.
    """
    sha = _run_git("rev-parse", "HEAD")
    if sha is None:
        return None, None
    status = _run_git("status", "--porcelain")
    return sha, (bool(status) if status is not None else None)


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in TRACKED_PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _gpu_info() -> dict[str, Any]:
    """Describe available CUDA devices, without pretending one exists."""
    try:
        import torch
    except ImportError:
        return {"available": False, "reason": "torch not installed", "devices": []}

    if not torch.cuda.is_available():
        return {
            "available": False,
            "reason": "no CUDA device visible to torch",
            "devices": [],
            "torch_version": torch.__version__,
        }

    devices = [
        {
            "index": index,
            "name": torch.cuda.get_device_name(index),
            "total_memory_bytes": torch.cuda.get_device_properties(index).total_memory,
            "capability": ".".join(str(c) for c in torch.cuda.get_device_capability(index)),
        }
        for index in range(torch.cuda.device_count())
    ]
    return {
        "available": True,
        "devices": devices,
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
    }


def capture_environment(*, seed: int | None = None) -> EnvironmentRecord:
    """Capture a complete environment record.

    Args:
        seed: The global seed in force, if one has been set.

    Returns:
        A populated :class:`EnvironmentRecord`. Every field is filled; unavailability is
        recorded explicitly rather than by omission.
    """
    sha, dirty = git_commit()
    return EnvironmentRecord(
        captured_at=datetime.now(UTC).isoformat(),
        python_version=sys.version,
        python_implementation=platform.python_implementation(),
        platform=platform.platform(),
        processor=platform.processor() or "unknown",
        packages=_package_versions(),
        git_commit=sha,
        git_dirty=dirty,
        gpu=_gpu_info(),
        seed=seed,
    )
