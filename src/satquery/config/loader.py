"""Hierarchical YAML configuration loading.

One typed :class:`~satquery.config.schema.Config` object is assembled from the per-concern
files in ``configs/``. Nothing in ``src/`` reads a YAML file directly, and no parameter is
hardcoded (CLAUDE.md §8).

Precedence, lowest to highest:

1. Schema defaults (which encode the CLAUDE.md §1 frozen facts).
2. ``configs/<section>.yaml``.
3. Explicit overrides passed to :func:`load_config`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from satquery.config.schema import Config
from satquery.exceptions import ConfigError
from satquery.utils.paths import configs_dir

__all__ = ["SECTION_FILES", "load_config", "load_yaml"]

#: Config section -> filename in ``configs/``. Sections absent from disk fall back to their
#: schema defaults; a section present but unparseable is an error.
SECTION_FILES: dict[str, str] = {
    "project": "project.yaml",
    "logging": "logging.yaml",
    "data": "data.yaml",
    "preprocessing": "preprocessing.yaml",
    "taxonomy": "taxonomy.yaml",
    "m1": "m1.yaml",
    "m2": "m2.yaml",
    "eval": "eval.yaml",
}


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a single YAML file into a mapping.

    Args:
        path: File to read.

    Returns:
        The parsed mapping. An empty file yields an empty dict.

    Raises:
        ConfigError: If the file is missing, is not valid YAML, or does not contain a mapping
            at the top level.
    """
    if not path.is_file():
        raise ConfigError("config file not found", path=str(path))

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError("config file is not valid YAML", path=str(path), reason=str(exc)) from exc
    except OSError as exc:
        raise ConfigError("config file could not be read", path=str(path), reason=str(exc)) from exc

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(
            "config file must contain a mapping at the top level",
            path=str(path),
            found_type=type(raw).__name__,
        )
    return raw


def load_config(
    *,
    config_dir: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> Config:
    """Assemble and validate the full typed configuration.

    Args:
        config_dir: Directory holding the section YAML files. Defaults to ``configs/``.
        overrides: Nested mapping of ``{section: {key: value}}`` applied on top of the files.

    Returns:
        A validated :class:`~satquery.config.schema.Config`.

    Raises:
        ConfigError: If a section file is malformed, or if the assembled configuration fails
            schema validation. The error context names the offending fields.
    """
    directory = config_dir if config_dir is not None else configs_dir()

    if not directory.is_dir():
        raise ConfigError("config directory not found", path=str(directory))

    merged: dict[str, Any] = {}
    for section, filename in SECTION_FILES.items():
        path = directory / filename
        if path.is_file():
            merged[section] = load_yaml(path)

    for section, values in (overrides or {}).items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section] = {**merged[section], **values}
        else:
            merged[section] = values

    try:
        return Config.model_validate(merged)
    except ValidationError as exc:
        problems = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "problem": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        raise ConfigError(
            "configuration failed schema validation",
            config_dir=str(directory),
            error_count=len(problems),
            problems=problems,
        ) from exc
