"""Typed, hierarchical configuration.

CLAUDE.md §8: all important parameters live in ``configs/*.yaml``; no magic numbers in
``src/``. Nothing outside this package reads a YAML file directly.
"""

from __future__ import annotations

from satquery.config.loader import load_config, load_yaml
from satquery.config.schema import Config

__all__ = ["Config", "load_config", "load_yaml"]
