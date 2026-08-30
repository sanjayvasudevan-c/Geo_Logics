"""CORINE hierarchy and the L3 -> requested-level aggregation (M2 step 0).

**The aggregation-before-geometry guarantee.** Hierarchy aggregation happens *before*
connected-component analysis, so one conceptual region is never counted as several because its
Level-3 subclasses differ. A city split into continuous (111) and discontinuous (112) urban
fabric is ONE urban region. :func:`~satquery.taxonomy.core.Taxonomy.mask_for` enforces the
order by construction — it aggregates, then returns the mask components run on.
IMPLEMENTATION_MAP §5.3 ranks a wrong aggregation table as the second most damaging silent
failure in the system.
"""

from __future__ import annotations

from satquery.taxonomy.core import (
    LEVELS,
    NO_EQUIVALENT,
    UNCLASSIFIED,
    ClassEntry,
    Level,
    Taxonomy,
    load_taxonomy,
)
from satquery.taxonomy.synonyms import Resolution, SynonymTable, load_synonyms

__all__ = [
    "LEVELS",
    "NO_EQUIVALENT",
    "UNCLASSIFIED",
    "ClassEntry",
    "Level",
    "Resolution",
    "SynonymTable",
    "Taxonomy",
    "load_synonyms",
    "load_taxonomy",
]
