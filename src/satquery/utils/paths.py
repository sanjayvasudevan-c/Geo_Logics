"""Project path resolution.

CLAUDE.md §9 forbids hardcoded paths. Every path in the system is derived from the project
root, which is located by walking upwards for the ``pyproject.toml`` marker rather than being
written down anywhere.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from satquery.exceptions import ConfigError

__all__ = ["configs_dir", "project_root", "reports_dir", "runs_dir"]

_ROOT_MARKER = "pyproject.toml"


@lru_cache(maxsize=1)
def project_root() -> Path:
    """Locate the repository root.

    Walks upwards from this file looking for ``pyproject.toml``.

    Returns:
        Resolved absolute path to the project root.

    Raises:
        ConfigError: If no marker is found in any parent directory.
    """
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / _ROOT_MARKER).is_file():
            return candidate
    raise ConfigError(
        "could not locate project root",
        marker=_ROOT_MARKER,
        searched_from=str(here),
    )


def configs_dir() -> Path:
    """Directory holding the hierarchical YAML configuration."""
    return project_root() / "configs"


def reports_dir() -> Path:
    """Directory holding experiment, evaluation and error-analysis reports."""
    return project_root() / "reports"


def runs_dir() -> Path:
    """Directory holding per-run artifact registries (``reports/runs/<run_id>/``)."""
    return reports_dir() / "runs"
