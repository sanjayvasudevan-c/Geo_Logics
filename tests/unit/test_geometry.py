"""M2 geometry engine: exact arithmetic on SYNTHETIC masks with known answers.

All class maps here are SYNTHETIC (CLAUDE.md §7): small hand-built arrays of CORINE codes whose
correct answers are known by construction, so every assertion checks arithmetic rather than
plausibility. No real reBEN reference maps are read.

The discriminating case is `TestConnectivity::test_diagonal_checkerboard`: a diagonal chain is
one component under 8-connectivity and N under 4-connectivity. That single fixture is why
connectivity has to be *fitted* rather than assumed — it swings every counting answer.
"""

from __future__ import annotations

import numpy as np
import pytest

from satquery.config.schema import M2Config
from satquery.exceptions import GeometryError
from satquery.geometry import (
    COMPASS,
    GeometryParams,
    compute_adjacency,
    compute_area,
    compute_count,
    compute_presence,
    compute_referring_box,
    compute_referring_point,
    compute_relative_position,
    extract_regions,
)
from satquery.taxonomy import load_taxonomy

pytestmark = pytest.mark.unit

URBAN, ARABLE, FOREST, WATER = 112, 211, 312, 512


@pytest.fixture(scope="module")
def tax():
    return load_taxonomy()


@pytest.fixture
def params():
    """Fully fitted parameters: 8-connectivity, no cleanup, MMU 0."""
    return GeometryParams(
        connectivity=8, min_mapping_unit_px=0, opening_kernel_px=0,
        adjacency_dilation_px=1, gsd_m=10.0,
    )


@pytest.fixture
def cfg():
    return M2Config()


def _map(rows: list[list[int]]) -> np.ndarray:
    """SYNTHETIC CORINE class map."""
    return np.array(rows, dtype=np.int32)


class TestUnfittedParametersRefuse:
    """A guessed convention is worse than a loud failure (CLAUDE.md §5)."""

    def test_missing_connectivity_raises(self, tax) -> None:
        bad = GeometryParams(min_mapping_unit_px=0, opening_kernel_px=0)
        with pytest.raises(GeometryError) as e:
            extract_regions(_map([[URBAN]]), "Urban fabric", "c19", tax, bad)
        assert "connectivity" in e.value.context["missing"]

    def test_missing_dilation_raises(self, tax) -> None:
        bad = GeometryParams(connectivity=8, min_mapping_unit_px=0, opening_kernel_px=0)
        with pytest.raises(GeometryError) as e:
            compute_adjacency(_map([[URBAN]]), "Urban fabric", "Arable land", "c19", tax, bad)
        assert "adjacency_dilation_px" in e.value.context["missing"]

    def test_default_config_is_unfitted(self, cfg) -> None:
        p = GeometryParams.from_config(cfg)
        assert p.connectivity is None and p.min_mapping_unit_px is None


class TestConnectivity:
    def test_diagonal_checkerboard(self, tax, params) -> None:
        """THE discriminating case: 1 component under 8-conn, 3 under 4-conn."""
        m = _map([
            [URBAN, ARABLE, ARABLE],
            [ARABLE, URBAN, ARABLE],
            [ARABLE, ARABLE, URBAN],
        ])
        eight = extract_regions(m, "Urban fabric", "c19", tax, params)
        four = extract_regions(
            m, "Urban fabric", "c19", tax,
            GeometryParams(connectivity=4, min_mapping_unit_px=0, opening_kernel_px=0),
        )
        assert len(eight) == 1, "diagonal chain is ONE component under 8-connectivity"
        assert len(four) == 3, "diagonal chain is THREE components under 4-connectivity"

    def test_orthogonal_chain_is_one_under_both(self, tax, params) -> None:
        m = _map([[URBAN, URBAN, URBAN], [ARABLE, ARABLE, ARABLE]])
        for c in (4, 8):
            p = GeometryParams(connectivity=c, min_mapping_unit_px=0, opening_kernel_px=0)
            assert len(extract_regions(m, "Urban fabric", "c19", tax, p)) == 1

    def test_invalid_connectivity_raises(self, tax) -> None:
        p = GeometryParams(connectivity=6, min_mapping_unit_px=0, opening_kernel_px=0)
        with pytest.raises(GeometryError):
            extract_regions(_map([[URBAN]]), "Urban fabric", "c19", tax, p)


class TestAggregationBeforeComponents:
    def test_adjacent_l3_siblings_are_one_component(self, tax, params) -> None:
        """111 + 112 side by side is ONE urban region (IMPLEMENTATION_MAP §5.3)."""
        m = _map([
            [111, 111, 112, 112],
            [111, 111, 112, 112],
            [ARABLE] * 4,
            [ARABLE] * 4,
        ])
        assert len(extract_regions(m, "Urban fabric", "c19", tax, params)) == 1

    def test_same_at_level_1(self, tax, params) -> None:
        m = _map([[111, 121], [131, 141]])
        assert len(extract_regions(m, "Artificial surfaces", "l1", tax, params)) == 1


class TestCounting:
    def test_two_separated_regions(self, tax, params) -> None:
        m = _map([
            [URBAN, ARABLE, ARABLE, URBAN],
            [URBAN, ARABLE, ARABLE, URBAN],
        ])
        assert compute_count(extract_regions(m, "Urban fabric", "c19", tax, params)).count == 2

    def test_empty_mask_counts_zero(self, tax, params) -> None:
        m = _map([[ARABLE, ARABLE], [ARABLE, ARABLE]])
        r = extract_regions(m, "Urban fabric", "c19", tax, params)
        assert compute_count(r).count == 0
        assert compute_presence(r).present is False

    def test_full_image_is_one_region(self, tax, params) -> None:
        m = _map([[URBAN] * 4] * 4)
        r = extract_regions(m, "Urban fabric", "c19", tax, params)
        assert compute_count(r).count == 1
        assert r.coverage == 1.0

    def test_single_pixel(self, tax, params) -> None:
        m = _map([[URBAN, ARABLE], [ARABLE, ARABLE]])
        assert compute_count(extract_regions(m, "Urban fabric", "c19", tax, params)).count == 1

    def test_ring_shape_is_one_region_and_holes_are_filled(self, tax, params) -> None:
        m = _map([
            [URBAN, URBAN, URBAN],
            [URBAN, ARABLE, URBAN],
            [URBAN, URBAN, URBAN],
        ])
        r = extract_regions(m, "Urban fabric", "c19", tax, params)
        assert compute_count(r).count == 1
        assert r.area_px == 9, "fill_holes must close the interior hole"


class TestMMU:
    def test_mmu_removes_small_blob_and_keeps_large(self, tax) -> None:
        m = _map([
            [URBAN, URBAN, URBAN, ARABLE, ARABLE, ARABLE],
            [URBAN, URBAN, URBAN, ARABLE, ARABLE, ARABLE],
            [URBAN, URBAN, URBAN, ARABLE, ARABLE, ARABLE],
            [ARABLE, ARABLE, ARABLE, ARABLE, ARABLE, URBAN],
        ])
        p = GeometryParams(connectivity=8, min_mapping_unit_px=4, opening_kernel_px=0)
        r = extract_regions(m, "Urban fabric", "c19", tax, p)
        assert len(r) == 1, "the 9-px block survives, the 1-px blob does not"
        assert r.dropped_below_mmu == 1
        assert r.regions[0].area_px == 9

    def test_mmu_zero_keeps_everything(self, tax, params) -> None:
        m = _map([[URBAN, ARABLE, URBAN]])
        assert len(extract_regions(m, "Urban fabric", "c19", tax, params)) == 2


class TestArea:
    def test_area_arithmetic_is_exact(self, tax, params) -> None:
        """12 pixels at 10 m GSD is exactly 1,200 m²."""
        m = _map([[URBAN] * 4] * 3)
        a = compute_area(extract_regions(m, "Urban fabric", "c19", tax, params))
        assert a.area_px == 12
        assert a.area_m2 == pytest.approx(12 * 100.0)
        assert a.coverage == pytest.approx(1.0)

    def test_coverage_is_exact_not_binned(self, tax, params) -> None:
        """S3 GR-2: binning is a FITTED convention, applied downstream, not here."""
        m = _map([[URBAN, ARABLE, ARABLE, ARABLE]])
        a = compute_area(extract_regions(m, "Urban fabric", "c19", tax, params))
        assert a.coverage == pytest.approx(0.25)
        assert a.coverage_pct == pytest.approx(25.0)

    def test_patch_area_matches_the_benchmark_constant(self, tax, params) -> None:
        """120x120 at 10 m is 1,440,000 m² — the value S3 found as the 100% bin."""
        m = _map([[URBAN] * 120] * 120)
        assert compute_area(
            extract_regions(m, "Urban fabric", "c19", tax, params)
        ).area_m2 == pytest.approx(1_440_000.0)


class TestAdjacency:
    def _pair(self, gap: int) -> np.ndarray:
        row = [URBAN] + [ARABLE] * gap + [WATER]
        return _map([row])

    def test_touching_classes_are_adjacent_at_k1(self, tax, params) -> None:
        m = _map([[URBAN, WATER]])
        assert compute_adjacency(m, "Urban fabric", "Inland waters", "c19", tax, params).adjacent

    def test_one_pixel_gap_needs_k2(self, tax) -> None:
        m = self._pair(gap=1)
        k1 = GeometryParams(connectivity=8, min_mapping_unit_px=0, opening_kernel_px=0,
                            adjacency_dilation_px=1)
        k2 = GeometryParams(connectivity=8, min_mapping_unit_px=0, opening_kernel_px=0,
                            adjacency_dilation_px=2)
        assert not compute_adjacency(m, "Urban fabric", "Inland waters", "c19", tax, k1).adjacent
        assert compute_adjacency(m, "Urban fabric", "Inland waters", "c19", tax, k2).adjacent

    def test_far_apart_stays_non_adjacent(self, tax, params) -> None:
        m = self._pair(gap=8)
        assert not compute_adjacency(
            m, "Urban fabric", "Inland waters", "c19", tax, params
        ).adjacent

    def test_adjacency_is_symmetric_for_touching_classes(self, tax, params) -> None:
        m = _map([[URBAN, WATER]])
        ab = compute_adjacency(m, "Urban fabric", "Inland waters", "c19", tax, params)
        ba = compute_adjacency(m, "Inland waters", "Urban fabric", "c19", tax, params)
        assert ab.adjacent == ba.adjacent

    def test_result_records_the_radius_used(self, tax, params) -> None:
        m = _map([[URBAN, WATER]])
        assert compute_adjacency(
            m, "Urban fabric", "Inland waters", "c19", tax, params
        ).dilation_px == 1


class TestRelativePosition:
    @pytest.mark.parametrize(
        ("dr", "dc", "expected"),
        [(-3, 0, "N"), (-3, 3, "NE"), (0, 3, "E"), (3, 3, "SE"),
         (3, 0, "S"), (3, -3, "SW"), (0, -3, "W"), (-3, -3, "NW")],
    )
    def test_eight_compass_directions(self, tax, params, dr, dc, expected) -> None:
        """Row increases downward, so North is decreasing row."""
        grid = np.full((9, 9), ARABLE, dtype=np.int32)
        cr, cc = 4, 4
        grid[cr, cc] = WATER                       # B at centre
        grid[cr + dr, cc + dc] = URBAN             # A offset
        a = extract_regions(grid, "Urban fabric", "c19", tax, params)
        b = extract_regions(grid, "Inland waters", "c19", tax, params)
        assert compute_relative_position(a, b).direction == expected

    def test_all_directions_are_in_the_compass(self) -> None:
        assert len(COMPASS) == 8
        assert COMPASS[0] == "N"

    def test_missing_class_is_invalid_not_a_guess(self, tax, params) -> None:
        m = _map([[URBAN, URBAN]])
        a = extract_regions(m, "Urban fabric", "c19", tax, params)
        b = extract_regions(m, "Inland waters", "c19", tax, params)
        assert compute_relative_position(a, b).valid is False


class TestReferring:
    def test_selects_largest_and_smallest(self, tax, params, cfg) -> None:
        grid = np.full((20, 20), ARABLE, dtype=np.int32)
        grid[1:7, 1:7] = URBAN       # 36 px = 9%
        grid[12:16, 12:16] = URBAN   # 16 px = 4%... below 1%? no, 4% -> valid
        r = extract_regions(grid, "Urban fabric", "c19", tax, params)
        big = compute_referring_box(r, "largest", cfg)
        small = compute_referring_box(r, "smallest", cfg)
        assert big.region is not None and small.region is not None
        assert big.region.area_px == 36
        assert small.region.area_px == 16

    def test_area_filter_excludes_oversized_instances(self, tax, params, cfg) -> None:
        """The benchmark's candidates cover 1%-50%; a full-image region is excluded."""
        grid = np.full((10, 10), URBAN, dtype=np.int32)
        r = extract_regions(grid, "Urban fabric", "c19", tax, params)
        out = compute_referring_box(r, "largest", cfg)
        assert out.region is None
        assert "filter" in out.reason

    def test_normalised_bbox_is_in_unit_range(self, tax, params, cfg) -> None:
        grid = np.full((20, 20), ARABLE, dtype=np.int32)
        grid[2:8, 2:8] = URBAN
        r = extract_regions(grid, "Urban fabric", "c19", tax, params)
        box = compute_referring_box(r, "largest", cfg).bbox_normalised
        assert box is not None
        assert all(0.0 <= v <= 1.0 for v in box)

    def test_referring_point_returns_the_containing_region(self, tax, params) -> None:
        grid = np.full((20, 20), ARABLE, dtype=np.int32)
        grid[2:8, 2:8] = URBAN
        out = compute_referring_point(grid, (5 / 19, 5 / 19), "c19", tax, params)
        assert out.region is not None
        assert out.region.area_px == 36

    def test_referring_point_on_other_class_finds_that_class(self, tax, params) -> None:
        grid = np.full((10, 10), ARABLE, dtype=np.int32)
        grid[0:3, 0:3] = URBAN
        out = compute_referring_point(grid, (0.9, 0.9), "c19", tax, params)
        assert out.region is not None, "the point lies in the arable region"

    def test_referring_point_outside_image(self, tax, params) -> None:
        grid = np.full((5, 5), URBAN, dtype=np.int32)
        assert compute_referring_point(grid, (5.0, 5.0), "c19", tax, params).region is None

    def test_referring_point_on_unclassified(self, tax, params) -> None:
        grid = np.full((5, 5), 999, dtype=np.int32)
        out = compute_referring_point(grid, (0.5, 0.5), "c19", tax, params)
        assert out.region is None
        assert "unclassified" in out.reason


class TestDeterminism:
    def test_same_input_gives_identical_output(self, tax, params) -> None:
        rng = np.random.default_rng(1337)
        codes = np.array([URBAN, ARABLE, FOREST, WATER])
        grid = codes[rng.integers(0, 4, size=(40, 40))].astype(np.int32)
        runs = [extract_regions(grid, "Urban fabric", "c19", tax, params) for _ in range(3)]
        assert len({len(r) for r in runs}) == 1
        assert all(np.array_equal(runs[0].mask, r.mask) for r in runs)
        assert all(r.regions == runs[0].regions for r in runs)

    def test_results_carry_the_params_that_produced_them(self, tax, params) -> None:
        """Auditability: the trace shows the convention, not just the number."""
        r = extract_regions(_map([[URBAN]]), "Urban fabric", "c19", tax, params)
        assert compute_count(r).params.connectivity == 8
        assert compute_area(r).params.gsd_m == 10.0


class TestNoLearnedComponent:
    def test_geometry_module_imports_no_ml_library(self) -> None:
        """CLAUDE.md §1: M2 contains no neural network. Enforced, not assumed."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[2] / "src" / "satquery" / "geometry"
        banned = ("import torch", "from torch", "sklearn", "lightgbm", "tensorflow")
        offenders = [
            f"{p.name}: {tok}"
            for p in root.rglob("*.py")
            for tok in banned
            if tok in p.read_text(encoding="utf-8")
        ]
        assert not offenders, f"learned component in M2: {offenders}"
