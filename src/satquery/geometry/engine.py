"""M2 — the symbolic geometry engine. Deterministic; **no neural network anywhere**.

`scipy.ndimage` + `skimage.measure` only (CLAUDE.md §1). This is where every scored *number*
originates: the number-flow rule (CLAUDE.md §2) says a language model may phrase an answer but
may never produce the value in it, and this module is the only producer.

**The pipeline order is fixed and load-bearing:**

```
class map -> hierarchy aggregation -> binary mask -> morphological cleanup
          -> connected components -> MMU filter -> region properties -> task computation
```

Aggregation happens **before** components, always. A city split into continuous (111) and
discontinuous (112) urban fabric is one region, not two; IMPLEMENTATION_MAP §5.3 ranks getting
that wrong as the second most damaging silent failure in the system. The order is enforced by
construction here — :func:`extract_regions` aggregates and masks before it labels, so a caller
cannot invert it through this API.

**Fitted parameters are not defaults.** Connectivity, MMU, opening radius and dilation radius
are *recovered* from ground-truth maps at S7, not guessed. Until they are fitted they are
``None``, and any operation needing one raises :class:`GeometryError` rather than silently
using a plausible value — a guessed connectivity swings every counting answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
from scipy import ndimage

from satquery.config.schema import M2Config
from satquery.exceptions import GeometryError
from satquery.taxonomy import Level, Taxonomy

__all__ = [
    "CARDINALS",
    "COMPASS",
    "DIAGONALS",
    "AdjacencyResult",
    "AreaResult",
    "CountResult",
    "GeometryParams",
    "PresenceResult",
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
    "quantise_bearing",
]

IntArray = npt.NDArray[np.integer[Any]]
BoolArray = npt.NDArray[np.bool_]

#: 8-way compass, ordered so index = round(angle / 45) with 0 = North.
COMPASS: tuple[str, ...] = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
#: Split out because the sectors are NOT equal width — see ``quantise_bearing``.
CARDINALS: tuple[str, ...] = ("N", "E", "S", "W")
DIAGONALS: tuple[str, ...] = ("NE", "SE", "SW", "NW")


def quantise_bearing(angle_deg: float, diagonal_band_deg: float) -> str:
    """Compass label for a bearing, under a diagonal sector of ``diagonal_band_deg`` width.

    The textbook 8-way compass uses eight equal 45-degree sectors, which is ``45`` here. The
    benchmark generator does **not**: its released answers are cardinal 81.60% of the time
    while cardinals are only ~62% of the offered options, so its diagonal sectors are much
    narrower. The width is therefore a fitted parameter, not a constant (S7 addendum).

    Args:
        angle_deg: Bearing with North at 0, increasing clockwise.
        diagonal_band_deg: Total angular width of each diagonal sector, in [0, 90].
            ``45`` gives equal sectors; ``0`` collapses to pure cardinals.

    Returns:
        One of the eight compass labels.
    """
    a = angle_deg % 360.0
    if abs((a % 90.0) - 45.0) <= diagonal_band_deg / 2.0:
        return DIAGONALS[int(a // 90.0) % 4]
    return CARDINALS[int(round(a / 90.0)) % 4]


@dataclass(frozen=True)
class GeometryParams:
    """The fitted parameters that produced a result.

    Carried on every output so an answer is auditable: the trace shows not just the number but
    the convention that generated it.
    """

    connectivity: int | None = None
    min_mapping_unit_px: int | None = None
    opening_kernel_px: int | None = None
    adjacency_dilation_px: int | None = None
    diagonal_band_deg: float | None = None
    direction_reference_rule: str | None = None
    gsd_m: float = 10.0

    @classmethod
    def from_config(cls, cfg: M2Config, *, gsd_m: float = 10.0) -> GeometryParams:
        """Build from the validated M2 config."""
        return cls(
            connectivity=cfg.connectivity,
            min_mapping_unit_px=cfg.min_mapping_unit_px,
            opening_kernel_px=cfg.opening_kernel_px,
            adjacency_dilation_px=cfg.adjacency_dilation_px,
            diagonal_band_deg=cfg.diagonal_band_deg,
            direction_reference_rule=cfg.direction_reference_rule,
            gsd_m=gsd_m,
        )

    def require(self, *names: str) -> None:
        """Raise unless every named parameter has been fitted.

        Args:
            *names: Attribute names that must not be ``None``.

        Raises:
            GeometryError: If any is unfitted. Silently substituting a default here would
                produce a confident wrong answer with a clean-looking trace.
        """
        missing = [n for n in names if getattr(self, n) is None]
        if missing:
            raise GeometryError(
                "geometry parameter not fitted; it is recovered from ground-truth maps at S7, "
                "never guessed",
                missing=missing,
            )


@dataclass(frozen=True)
class Region:
    """One connected component and its measured properties."""

    label: int
    area_px: int
    bbox: tuple[int, int, int, int]      # (row_min, col_min, row_max, col_max)
    centroid: tuple[float, float]        # (row, col)
    bbox_fill: float                     # area_px / bbox area, in (0, 1]

    def area_m2(self, gsd_m: float) -> float:
        """Ground area in square metres."""
        return self.area_px * gsd_m * gsd_m

    def normalised_bbox(self, shape: tuple[int, int]) -> tuple[float, float, float, float]:
        """Bbox as ``(x0, y0, x1, y1)`` in [0, 1], matching the benchmark's answer format."""
        h, w = shape
        r0, c0, r1, c1 = self.bbox
        return (c0 / w, r0 / h, c1 / w, r1 / h)


@dataclass(frozen=True)
class RegionSet:
    """The components surviving the full pipeline, plus the mask they came from."""

    regions: tuple[Region, ...]
    mask: BoolArray
    shape: tuple[int, int]
    params: GeometryParams
    level: Level
    class_query: str | int
    dropped_below_mmu: int = 0
    total_px: int = 0

    def __len__(self) -> int:
        return len(self.regions)

    @property
    def area_px(self) -> int:
        """Total pixels across surviving components."""
        return sum(r.area_px for r in self.regions)

    @property
    def coverage(self) -> float:
        """Fraction of the image covered, in [0, 1]."""
        return self.area_px / (self.shape[0] * self.shape[1]) if self.shape[0] else 0.0


def _structure(connectivity: int) -> IntArray:
    """`scipy.ndimage` structuring element for 4- or 8-connectivity."""
    if connectivity in (4, 8):
        rank = 1 if connectivity == 4 else 2
        struct: IntArray = np.asarray(ndimage.generate_binary_structure(2, rank), dtype=np.int8)
        return struct
    raise GeometryError("connectivity must be 4 or 8", connectivity=connectivity)


def _disk(radius: int) -> BoolArray:
    """Disk structuring element of the given radius; radius 0 yields a single pixel."""
    if radius <= 0:
        return np.ones((1, 1), dtype=bool)
    size = 2 * radius + 1
    yy, xx = np.ogrid[-radius : radius + 1, -radius : radius + 1]
    disk: BoolArray = (yy * yy + xx * xx) <= radius * radius
    return disk.reshape(size, size)


def extract_regions(
    class_map: IntArray,
    class_query: str | int,
    level: Level,
    taxonomy: Taxonomy,
    params: GeometryParams,
    *,
    fill_holes: bool = True,
) -> RegionSet:
    """Run the full pipeline for one class at one level.

    **Aggregation happens before components, by construction.** The mask is taken from the
    *aggregated* map, so L3 siblings merge into one region rather than being counted separately.

    Args:
        class_map: Integer array of CORINE codes.
        class_query: Class name or id at ``level``.
        level: Level the query is posed at.
        taxonomy: The loaded taxonomy.
        params: Fitted geometry parameters.
        fill_holes: Whether to fill interior holes after opening.

    Returns:
        The :class:`RegionSet`.

    Raises:
        GeometryError: If connectivity, MMU or opening radius is unfitted.
        TaxonomyError: If the class cannot be resolved at ``level``.
    """
    params.require("connectivity", "min_mapping_unit_px", "opening_kernel_px")
    assert params.connectivity is not None
    assert params.min_mapping_unit_px is not None
    assert params.opening_kernel_px is not None

    # STEP 0-1: aggregate to the queried level, THEN mask. Never the other way round.
    mask: BoolArray = taxonomy.mask_for(class_map, class_query, level)
    shape = (int(mask.shape[0]), int(mask.shape[1]))
    total_px = int(mask.sum())

    # STEP 2: morphological cleanup.
    if params.opening_kernel_px > 0:
        mask = ndimage.binary_opening(mask, structure=_disk(params.opening_kernel_px))
    if fill_holes:
        mask = ndimage.binary_fill_holes(mask)
        if mask is None:  # pragma: no cover - defensive
            raise GeometryError("binary_fill_holes returned nothing", shape=shape)

    # STEP 3: connected components.
    labelled, n = ndimage.label(mask, structure=_structure(params.connectivity))
    labelled = np.asarray(labelled)

    # STEP 4-5: MMU filter, then region properties.
    #
    # PERFORMANCE: skimage.regionprops over every component plus np.isin over every label is
    # O(pixels x components) and measured 163.89 ms/call on a fragmented 120x120 map — which
    # projects to ~4.3 HOURS for S8's oracle sweep. Both are replaced with linear-time
    # primitives: bincount for areas, find_objects for bounding boxes, and a lookup table for
    # the surviving mask. Only components that survive the MMU filter are measured at all.
    regions: list[Region] = []
    dropped = 0
    if n:
        areas = np.bincount(labelled.ravel(), minlength=n + 1)
        boxes = ndimage.find_objects(labelled)
        keep_lut = np.zeros(n + 1, dtype=bool)
        for label in range(1, n + 1):
            area = int(areas[label])
            if area < params.min_mapping_unit_px:
                dropped += 1
                continue
            box = boxes[label - 1]
            if box is None:  # pragma: no cover - label absent from the array
                continue
            rs, cs = box
            r0, r1, c0, c1 = rs.start, rs.stop, cs.start, cs.stop
            sub = labelled[rs, cs] == label
            rows, cols = np.nonzero(sub)
            keep_lut[label] = True
            regions.append(
                Region(
                    label=label, area_px=area, bbox=(int(r0), int(c0), int(r1), int(c1)),
                    centroid=(float(rows.mean() + r0), float(cols.mean() + c0)),
                    bbox_fill=area / max((r1 - r0) * (c1 - c0), 1),
                )
            )
        surviving: BoolArray = keep_lut[labelled]
    else:
        surviving = np.zeros(shape, dtype=bool)

    return RegionSet(
        regions=tuple(regions), mask=surviving, shape=shape, params=params,
        level=level, class_query=class_query, dropped_below_mmu=dropped, total_px=total_px,
    )


# --------------------------------------------------------------------------- task results
@dataclass(frozen=True)
class PresenceResult:
    """Whether the class is present."""

    present: bool
    n_regions: int
    params: GeometryParams


@dataclass(frozen=True)
class CountResult:
    """Number of surviving connected regions."""

    count: int
    dropped_below_mmu: int
    params: GeometryParams


@dataclass(frozen=True)
class AreaResult:
    """Area of the class, in every unit the benchmark uses.

    S3 measured that the benchmark quantises area to **11 decile bins**: the only values that
    occur are 0,10,…,100 percent, equivalently 0,144000,…,1440000 m² for a 120x120 patch at
    10 m. So the exact coverage is computed here and binned separately, rather than rounded.
    """

    area_px: int
    area_m2: float
    coverage: float          # exact fraction in [0, 1]
    coverage_pct: float      # exact percent in [0, 100]
    params: GeometryParams


@dataclass(frozen=True)
class AdjacencyResult:
    """Whether two classes touch, under the fitted dilation radius."""

    adjacent: bool
    dilation_px: int
    overlap_px: int
    params: GeometryParams


@dataclass(frozen=True)
class RelativePositionResult:
    """Compass direction of A relative to B, from centroid offset."""

    direction: str
    delta_row: float
    delta_col: float
    params: GeometryParams
    valid: bool = True


@dataclass(frozen=True)
class ReferringResult:
    """A selected region and its normalised bounding box."""

    region: Region | None
    bbox_normalised: tuple[float, float, float, float] | None
    n_candidates: int
    qualifier: str | None
    params: GeometryParams
    reason: str = ""


def compute_presence(regions: RegionSet) -> PresenceResult:
    """Presence is a non-empty component set."""
    return PresenceResult(
        present=len(regions) > 0, n_regions=len(regions), params=regions.params
    )


def compute_count(regions: RegionSet) -> CountResult:
    """Count is the number of surviving components."""
    return CountResult(
        count=len(regions), dropped_below_mmu=regions.dropped_below_mmu,
        params=regions.params,
    )


def compute_area(regions: RegionSet) -> AreaResult:
    """Area in pixels, square metres, and exact coverage.

    Binning to the benchmark's decile grid is deliberately **not** done here — the bin boundary
    convention is a fitted parameter (S3 GR-2), so binning lives with the answer-format layer
    where that convention is applied explicitly.
    """
    gsd = regions.params.gsd_m
    return AreaResult(
        area_px=regions.area_px,
        area_m2=regions.area_px * gsd * gsd,
        coverage=regions.coverage,
        coverage_pct=100.0 * regions.coverage,
        params=regions.params,
    )


def compute_adjacency(
    class_map: IntArray,
    class_a: str | int,
    class_b: str | int,
    level: Level,
    taxonomy: Taxonomy,
    params: GeometryParams,
) -> AdjacencyResult:
    """Whether two classes touch: ``binary_dilation(A, k) ∩ B`` non-empty.

    Raises:
        GeometryError: If the dilation radius is unfitted.
    """
    params.require("adjacency_dilation_px")
    assert params.adjacency_dilation_px is not None
    mask_a: BoolArray = taxonomy.mask_for(class_map, class_a, level)
    mask_b: BoolArray = taxonomy.mask_for(class_map, class_b, level)
    dilated = ndimage.binary_dilation(mask_a, structure=_disk(params.adjacency_dilation_px))
    overlap = int(np.logical_and(dilated, mask_b).sum())
    return AdjacencyResult(
        adjacent=overlap > 0, dilation_px=params.adjacency_dilation_px,
        overlap_px=overlap, params=params,
    )


def compute_relative_position(
    regions_a: RegionSet, regions_b: RegionSet
) -> RelativePositionResult:
    """Compass direction of A relative to B, under the fitted direction convention.

    Row increases downward in image coordinates, so North is decreasing row. Two fitted
    parameters govern the result: which point stands for a multi-component class
    (``direction_reference_rule``) and how wide the diagonal sectors are
    (``diagonal_band_deg``). Both were recovered at the S7 addendum; see ``configs/m2.yaml``
    for what is measured and what is under-determined.

    **This function does not decide which class is the subject.** ``regions_a`` is the subject
    and ``regions_b`` the reference; resolving that from a question's wording is the parser's
    job, because several templates invert it (S7 addendum, ``oracle.subject_is_second``).

    Raises:
        GeometryError: If the direction convention is unfitted.
    """
    regions_a.params.require("diagonal_band_deg", "direction_reference_rule")
    band = regions_a.params.diagonal_band_deg
    rule = regions_a.params.direction_reference_rule
    assert band is not None and rule is not None

    if not regions_a.regions or not regions_b.regions:
        return RelativePositionResult(
            direction="", delta_row=0.0, delta_col=0.0, params=regions_a.params, valid=False
        )

    def reference_point(rs: RegionSet) -> tuple[float, float]:
        if rule == "largest_component":
            return max(rs.regions, key=lambda r: r.area_px).centroid
        if rule == "bbox_centre":
            r0 = min(r.bbox[0] for r in rs.regions)
            c0 = min(r.bbox[1] for r in rs.regions)
            r1 = max(r.bbox[2] for r in rs.regions)
            c1 = max(r.bbox[3] for r in rs.regions)
            return ((r0 + r1) / 2.0, (c0 + c1) / 2.0)
        total = sum(r.area_px for r in rs.regions)
        return (sum(r.centroid[0] * r.area_px for r in rs.regions) / total,
                sum(r.centroid[1] * r.area_px for r in rs.regions) / total)

    ar, ac = reference_point(regions_a)
    br, bc = reference_point(regions_b)
    d_row, d_col = ar - br, ac - bc
    if d_row == 0 and d_col == 0:
        return RelativePositionResult(
            direction="", delta_row=0.0, delta_col=0.0, params=regions_a.params, valid=False
        )
    # atan2 with North at 0 and angles increasing clockwise (N -> NE -> E ...).
    angle = float(np.degrees(np.arctan2(d_col, -d_row)) % 360.0)
    return RelativePositionResult(
        direction=quantise_bearing(angle, band),
        delta_row=float(d_row), delta_col=float(d_col), params=regions_a.params,
    )


def compute_referring_box(
    regions: RegionSet,
    qualifier: Literal["largest", "smallest"] | None,
    cfg: M2Config,
) -> ReferringResult:
    """Select a region by qualifier, after the benchmark's instance filters.

    VERIFIED from the benchmark generator: candidate instances cover **1%-50% of image area**
    and fill **at least 40% of their bounding box**. Those filters remove wrong candidates for
    free, which is why referring expressions are a strong sub-task.
    """
    image_px = regions.shape[0] * regions.shape[1]
    candidates = [
        r for r in regions.regions
        if cfg.referring_area_min <= r.area_px / image_px <= cfg.referring_area_max
        and r.bbox_fill >= cfg.referring_bbox_fill_min
    ]
    if not candidates:
        return ReferringResult(
            region=None, bbox_normalised=None, n_candidates=0, qualifier=qualifier,
            params=regions.params, reason="no instance passed the area / bbox-fill filters",
        )
    chosen = (
        min(candidates, key=lambda r: (r.area_px, r.label))
        if qualifier == "smallest"
        else max(candidates, key=lambda r: (r.area_px, -r.label))
    )
    return ReferringResult(
        region=chosen, bbox_normalised=chosen.normalised_bbox(regions.shape),
        n_candidates=len(candidates), qualifier=qualifier, params=regions.params,
    )


def compute_referring_point(
    class_map: IntArray,
    point: tuple[float, float],
    level: Level,
    taxonomy: Taxonomy,
    params: GeometryParams,
) -> ReferringResult:
    """Bounding box of the component containing a given point.

    The benchmark supplies the point normalised to [0, 1] as ``(x, y)``. This is the cheapest
    of all the symbolic tasks — one component lookup — and Architecture A omitted it entirely.

    Args:
        class_map: Integer array of CORINE codes.
        point: ``(x, y)`` normalised to [0, 1].
        level: Level to aggregate to before labelling.
        taxonomy: The loaded taxonomy.
        params: Fitted geometry parameters.

    Returns:
        The containing region and its normalised bbox, or an empty result with a reason.
    """
    params.require("connectivity")
    assert params.connectivity is not None
    h, w = class_map.shape
    col = int(round(point[0] * (w - 1)))
    row = int(round(point[1] * (h - 1)))
    if not (0 <= row < h and 0 <= col < w):
        return ReferringResult(
            region=None, bbox_normalised=None, n_candidates=0, qualifier=None,
            params=params, reason=f"point {point} outside the image",
        )
    code = int(class_map[row, col])
    if code == taxonomy.unclassified_code:
        return ReferringResult(
            region=None, bbox_normalised=None, n_candidates=0, qualifier=None,
            params=params, reason="point falls on an unclassified pixel",
        )
    entry = taxonomy.by_code(code)
    target = entry.to_19 if level == "c19" and entry.to_19 else code
    if level == "c19" and entry.to_19 is None:
        return ReferringResult(
            region=None, bbox_normalised=None, n_candidates=0, qualifier=None, params=params,
            reason=f"class {code} has no 19-class equivalent",
        )
    found = extract_regions(class_map, target, level, taxonomy, params)
    if not found.mask[row, col]:
        return ReferringResult(
            region=None, bbox_normalised=None, n_candidates=len(found.regions), qualifier=None,
            params=params,
            reason="point is not inside any surviving component (removed by opening or MMU)",
        )
    # Re-label the surviving mask and read the label AT the point directly.
    labelled, _ = ndimage.label(found.mask, structure=_structure(params.connectivity))
    here = int(labelled[row, col])
    for region in found.regions:
        r0, c0, r1, c1 = region.bbox
        if r0 <= row < r1 and c0 <= col < c1 and int(labelled[row, col]) == here:
            sub = labelled[r0:r1, c0:c1]
            if here in np.unique(sub):
                return ReferringResult(
                    region=region, bbox_normalised=region.normalised_bbox(found.shape),
                    n_candidates=len(found.regions), qualifier=None, params=params,
                )
    return ReferringResult(
        region=None, bbox_normalised=None, n_candidates=len(found.regions), qualifier=None,
        params=params, reason="point is not inside any surviving component",
    )


@dataclass(frozen=True)
class CaptionAttributes:
    """The structured attribute set a caption is built from.

    VERIFIED tiers from the benchmark generator: primary >25% coverage, secondary 5-25%,
    marginal <5%.
    """

    per_class: dict[str, dict[str, Any]] = field(default_factory=dict)
    adjacencies: tuple[tuple[str, str], ...] = ()

    def tier_of(self, coverage: float) -> str:
        """Coverage tier name."""
        if coverage > 0.25:
            return "primary"
        if coverage >= 0.05:
            return "secondary"
        return "marginal"
