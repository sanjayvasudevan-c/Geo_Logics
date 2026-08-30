"""Natural-language surface form -> canonical class resolution.

The vocabulary is derived from real BigEarthNet.txt question text (S3/S4), not invented.
Observed and unobserved forms are kept apart in ``configs/synonyms.yaml`` so that measured
benchmark vocabulary is never confused with defensive additions for the demo path.

S3 established that questions are asked exclusively in the 19-class vocabulary, so the default
resolution level is ``c19``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from satquery.exceptions import TaxonomyError
from satquery.taxonomy.core import Level, Taxonomy, load_taxonomy
from satquery.utils.paths import project_root

__all__ = ["Resolution", "SynonymTable", "load_synonyms"]

SYNONYMS = "configs/synonyms.yaml"
_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    """Normalise a surface form: lowercase, collapse whitespace, drop commas and periods."""
    return _WS.sub(" ", text.lower().strip().rstrip(".").replace(",", "")).strip()


@dataclass(frozen=True)
class Resolution:
    """The outcome of resolving a surface form.

    Attributes:
        canonical: The canonical class name at ``level``.
        level: The level the class is expressed at.
        observed: Whether this form was measured in real benchmark question text. ``False``
            means it is a demo-path convenience, which callers may wish to report differently.
        approximate: Whether the mapping is a near-equivalent rather than exact (used by the
            Indian vocabulary layer, where e.g. "tank" is not exactly "Inland waters").
    """

    canonical: str
    level: Level
    observed: bool
    approximate: bool = False


class SynonymTable:
    """Resolves natural-language class mentions to canonical classes."""

    def __init__(self, raw: dict[str, Any], taxonomy: Taxonomy) -> None:
        self._taxonomy = taxonomy
        self.default_level: Level = raw.get("default_level", "c19")
        self._table: dict[str, Resolution] = {}
        self.unresolved: list[str] = list(raw.get("unresolved") or [])

        for observed_flag, section in ((True, "observed"), (False, "unobserved")):
            for key, spec in (raw.get(section) or {}).items():
                canonical = spec.get("resolves_to", key)
                level: Level = spec.get("level", self.default_level)
                approximate = bool(spec.get("approximate", False))
                # Validate against the taxonomy: a synonym pointing at a non-existent class is
                # a silent routing failure waiting to happen.
                taxonomy.resolve_query(canonical, level)
                for form in spec.get("forms", []):
                    self._table[_norm(str(form))] = Resolution(
                        canonical=canonical, level=level,
                        observed=observed_flag, approximate=approximate,
                    )
                self._table.setdefault(
                    _norm(canonical),
                    Resolution(canonical, level, observed_flag, approximate),
                )

    def __len__(self) -> int:
        return len(self._table)

    @property
    def forms(self) -> tuple[str, ...]:
        """Every registered surface form, normalised."""
        return tuple(sorted(self._table))

    def resolve(self, surface_form: str) -> Resolution:
        """Resolve a surface form to a canonical class.

        Args:
            surface_form: Text as it appeared in a question, e.g. ``"arable lands"``.

        Returns:
            The :class:`Resolution`.

        Raises:
            TaxonomyError: If the form is not registered. Callers must treat this as
                "unresolved, report it" — never as a silent miss.
        """
        key = _norm(surface_form)
        if key in self._table:
            return self._table[key]
        raise TaxonomyError(
            "unresolved surface form", surface_form=surface_form, normalised=key,
            hint="report it; do not silently drop it (STAGE_PROMPTS.md S4)",
        )

    def try_resolve(self, surface_form: str) -> Resolution | None:
        """Resolve, or return ``None`` if the form is unknown."""
        return self._table.get(_norm(surface_form))


@lru_cache(maxsize=1)
def load_synonyms(path: Path | None = None) -> SynonymTable:
    """Load and validate the synonym table.

    Args:
        path: Synonym YAML. Defaults to ``configs/synonyms.yaml``.

    Returns:
        A validated :class:`SynonymTable`.

    Raises:
        TaxonomyError: If the file is missing, or a synonym targets a class that does not exist.
    """
    target = path if path is not None else project_root() / SYNONYMS
    if not target.is_file():
        raise TaxonomyError("synonym table not found", path=str(target))
    raw: dict[str, Any] = yaml.safe_load(target.read_text(encoding="utf-8"))
    return SynonymTable(raw, load_taxonomy())
