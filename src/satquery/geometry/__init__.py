"""M2 — the symbolic geometry engine (pipeline stage 6).

Deterministic. `scipy.ndimage` + `skimage.measure` only. **No neural network anywhere**
(CLAUDE.md §1). This is the sole producer of every scored number in the system.
"""

from __future__ import annotations

from satquery.geometry.engine import (
    COMPASS,
    AdjacencyResult,
    AreaResult,
    CaptionAttributes,
    CountResult,
    GeometryParams,
    PresenceResult,
    ReferringResult,
    Region,
    RegionSet,
    RelativePositionResult,
    compute_adjacency,
    compute_area,
    compute_count,
    compute_presence,
    compute_referring_box,
    compute_referring_point,
    compute_relative_position,
    extract_regions,
)

__all__ = [
    "COMPASS",
    "AdjacencyResult",
    "AreaResult",
    "CaptionAttributes",
    "CountResult",
    "GeometryParams",
    "PresenceResult",
    "ReferringResult",
    "Region",
    "RegionSet",
    "RelativePositionResult",
    "compute_adjacency",
    "compute_area",
    "compute_count",
    "compute_presence",
    "compute_referring_box",
    "compute_referring_point",
    "compute_relative_position",
    "extract_regions",
]
