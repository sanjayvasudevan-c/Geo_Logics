"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from satquery.config.loader import load_config
from satquery.config.schema import Config
from satquery.utils.paths import configs_dir, project_root


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """The project root."""
    return project_root()


@pytest.fixture(scope="session")
def real_config_dir() -> Path:
    """The project's actual ``configs/`` directory."""
    return configs_dir()


@pytest.fixture
def config(real_config_dir: Path) -> Config:
    """The project's real configuration, loaded and validated."""
    return load_config(config_dir=real_config_dir)


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Iterator[Path]:
    """An empty directory for writing throwaway config files."""
    directory = tmp_path / "configs"
    directory.mkdir()
    yield directory
