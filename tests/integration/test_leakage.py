"""Leakage test suite for geographic block CV.

**These tests check the BINDING, not the label.** Asserting that every patch carries the fold
its block was assigned proves only that a dictionary lookup worked. The property that matters
is that no two *physically touching* patches were separated by the split — and a block scheme
can satisfy the first while violating the second whenever a boundary runs between two touching
patches. S6 measured exactly that: `grid_1deg` passes the label check and splits 8,769 touching
pairs; `s2_tile` splits zero.

Adjacency here is exact, not inferred. reBEN patch ids encode tile, row and column, so two
patches in the same tile differing by at most one in each are touching. No rounding is involved,
which is what makes this a real check rather than a proxy for one.

Synthetic frames in this module are SYNTHETIC (CLAUDE.md §7): small hand-built geographies with
known adjacency, so violations are detected against arithmetic rather than plausibility.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from satquery.data.splits import (
    STRATEGIES,
    adjacent_pairs_spanning_folds,
    all_adjacent_pairs,
    assign_folds,
    assign_folds_stratified,
    block_keys,
    haversine_km,
    load_manifest,
)
from satquery.evaluation.forensics import BENCH_SPLIT
from satquery.exceptions import ConfigError, ContractViolationError
from satquery.utils.paths import project_root

pytestmark = pytest.mark.integration

SPLIT_DIR = "data/processed/splits"
GEOGRAPHY = "data/processed/geography_train.parquet"


def _grid_frame(rows: int = 6, cols: int = 6, tile: str = "T33UUP") -> pd.DataFrame:
    """SYNTHETIC contiguous patch grid with known adjacency."""
    return pd.DataFrame([
        {
            "patch_id": f"S2A_X_{tile}_{r}_{c}", "tile": tile, "row": r, "col": c,
            "country": "Austria" if c < cols // 2 else "Serbia",
            "lat": 47.0 + r * 0.01, "lon": 12.0 + c * 0.01,
        }
        for r in range(rows) for c in range(cols)
    ])


class TestBlockIntegrity:
    """The LABEL check — necessary but far from sufficient."""

    @pytest.mark.parametrize("strategy", STRATEGIES)
    def test_no_block_spans_folds(self, strategy) -> None:
        # Each strategy needs at least k distinct blocks to be satisfiable. A single-tile,
        # single-degree-cell frame legitimately cannot supply that for s2_tile or grid_1deg,
        # so build a frame with two tiles spread across two 1-degree cells.
        a = _grid_frame(6, 6, "T33UUP")
        b = _grid_frame(6, 6, "T34TEN")
        b["lat"] = b["lat"] + 2.0
        b["lon"] = b["lon"] + 2.0
        frame = pd.concat([a, b], ignore_index=True)
        manifest = assign_folds(frame, strategy=strategy, k=2)
        assert manifest.blocks_spanning_folds() == []

    def test_assign_folds_refuses_fewer_blocks_than_folds(self) -> None:
        frame = _grid_frame(4, 4, tile="T33UUP")
        with pytest.raises(ConfigError) as e:
            assign_folds(frame, strategy="s2_tile", k=5)
        assert e.value.context["blocks"] == 1

    def test_deterministic_for_a_given_seed(self) -> None:
        frame = _grid_frame(8, 8)
        a = assign_folds(frame, strategy="country", k=2, seed=1337)
        b = assign_folds(frame, strategy="country", k=2, seed=1337)
        assert a.fold_of == b.fold_of

    def test_manifest_round_trips(self, tmp_path: Path) -> None:
        frame = _grid_frame(8, 8)
        written = assign_folds(frame, strategy="country", k=2)
        written.write(tmp_path / "m.json")
        assert load_manifest(tmp_path / "m.json").fold_of == written.fold_of


class TestGeographicLeakageBinding:
    """The BINDING check — the one that actually matters."""

    def test_detector_finds_a_planted_violation(self) -> None:
        """Guard against a detector that reports zero because it is broken."""
        frame = _grid_frame(4, 4)
        # Deliberately split two touching patches across folds.
        broken = type("M", (), {"fold_of": {
            str(p): (0 if (r + c) % 2 == 0 else 1)
            for p, r, c in zip(frame.patch_id, frame.row, frame.col, strict=True)
        }})()
        assert adjacent_pairs_spanning_folds(frame, broken), (
            "detector found no violations in a deliberately checkerboarded split — it is broken"
        )

    def test_tile_blocking_splits_no_touching_pair(self) -> None:
        frame = pd.concat([_grid_frame(5, 5, "T33UUP"), _grid_frame(5, 5, "T34TEN")])
        manifest = assign_folds(frame, strategy="s2_tile", k=2)
        assert adjacent_pairs_spanning_folds(frame, manifest) == []

    def test_country_blocking_can_split_touching_pairs(self) -> None:
        """A boundary running through a tile separates patches that physically touch.

        This is the failure the label check cannot see: every block is intact, yet neighbours
        are on opposite sides of the split.
        """
        frame = _grid_frame(6, 6)          # country boundary at col 3, mid-tile
        manifest = assign_folds(frame, strategy="country", k=2)
        assert manifest.blocks_spanning_folds() == [], "label check passes..."
        assert adjacent_pairs_spanning_folds(frame, manifest), "...binding check must not"

    def test_adjacency_counts_the_eight_neighbourhood(self) -> None:
        frame = _grid_frame(3, 3)
        # 3x3 grid: 12 orthogonal + 8 diagonal = 20 touching pairs.
        assert all_adjacent_pairs(frame) == 20

    def test_pair_denominator_is_pairs_not_patches(self) -> None:
        """A per-patch rate can exceed 100% because a patch has up to eight neighbours."""
        frame = _grid_frame(6, 6)
        assert all_adjacent_pairs(frame) > len(frame)


class TestDuplicateLeakage:
    def test_no_duplicate_patch_ids_within_the_real_split(self) -> None:
        path = project_root() / GEOGRAPHY
        if not path.is_file():
            pytest.skip("geography table not built")
        frame = pd.read_parquet(path)
        assert frame.patch_id.duplicated().sum() == 0

    def test_no_patch_assigned_to_two_folds(self) -> None:
        path = project_root() / SPLIT_DIR / "s2_tile_k5_seed1337.json"
        if not path.is_file():
            pytest.skip("split manifest not built")
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert len(raw["fold_of"]) == raw["n_patches"]

    def test_repeat_acquisitions_exist_and_are_contained_by_the_split(self) -> None:
        """reBEN images the same ground location on multiple dates — a real leakage hazard.

        MEASURED at S6: 115,040 distinct (tile, row, col) locations across 237,871 patches.
        69,479 locations carry repeat acquisitions, involving 192,310 patches — **80.8% of the
        training split** — up to 4 acquisitions of one location.

        Under a RANDOM split, 62,195 of those locations (89.5%) scatter their near-twins across
        the fold boundary. Under s2_tile blocking, zero do, because repeats share a tile and a
        tile cannot span folds. This test asserts that containment, not the absence of repeats.
        """
        path = project_root() / GEOGRAPHY
        manifest_path = project_root() / SPLIT_DIR / "s2_tile_k5_seed1337.json"
        if not (path.is_file() and manifest_path.is_file()):
            pytest.skip("geography table or split manifest not built")
        frame = pd.read_parquet(path)
        frame["fold"] = frame.patch_id.map(load_manifest(manifest_path).fold_of)

        counts = frame.groupby(["tile", "row", "col"]).size()
        repeats = counts[counts > 1]
        assert len(repeats) > 0, "expected repeat acquisitions; the hazard should be present"

        spread = frame.groupby(["tile", "row", "col"]).fold.nunique()
        spanning = spread[spread > 1]
        assert len(spanning) == 0, (
            f"{len(spanning):,} ground locations have repeat acquisitions in different folds — "
            "near-duplicate leakage across the split"
        )


class TestContamination:
    def test_split_manifests_contain_no_bench_patches(self) -> None:
        """The quarantined split must intersect nothing (CLAUDE.md §7)."""
        path = project_root() / SPLIT_DIR / "s2_tile_k5_seed1337.json"
        if not path.is_file():
            pytest.skip("split manifest not built")
        raw = json.loads(path.read_text(encoding="utf-8"))
        md = pd.read_parquet(
            project_root() / "data/raw/reben/metadata.parquet", columns=["patch_id", "split"]
        )
        non_train = set(md[md.split != "train"].patch_id)
        assert not (set(raw["fold_of"]) & non_train), (
            "split manifest contains patches from outside the training split"
        )

    def test_bench_is_not_a_reben_split_value(self) -> None:
        """reBEN's own metadata has no 'bench'; the quarantine lives in BigEarthNet.txt."""
        md = pd.read_parquet(
            project_root() / "data/raw/reben/metadata.parquet", columns=["split"]
        )
        assert BENCH_SPLIT not in set(md.split.unique())


class TestPreprocessingLeakage:
    def test_norm_stats_would_be_rejected_if_not_from_train(self) -> None:
        """Fitted statistics may only come from the training split (CLAUDE.md §7)."""
        from satquery.preprocessing.bands import CHANNEL_ORDER
        from satquery.preprocessing.norm_stats import BandStats, NormStats

        bad = NormStats(
            bands={b: BandStats(0.0, 1.0) for b in CHANNEL_ORDER},
            split="validation", split_hash="x", n_samples=1, computed_at="t",
        )
        with pytest.raises(ConfigError):
            bad.validate_complete()


class TestGeographicDistance:
    def test_haversine_known_distance(self) -> None:
        """London to Paris is ~344 km."""
        assert haversine_km(51.5074, -0.1278, 48.8566, 2.3522) == pytest.approx(344, abs=6)

    def test_zero_distance_for_identical_points(self) -> None:
        assert haversine_km(47.0, 12.0, 47.0, 12.0) == pytest.approx(0.0)


class TestBlockKeys:
    def test_grid_1deg_requires_coordinates(self) -> None:
        frame = _grid_frame(3, 3)
        frame.loc[0, "lat"] = None
        with pytest.raises(ConfigError) as e:
            block_keys(frame, "grid_1deg")
        assert e.value.context["missing"] == 1

    def test_unknown_strategy_raises(self) -> None:
        with pytest.raises(ConfigError):
            block_keys(_grid_frame(2, 2), "postcode")  # type: ignore[arg-type]

    def test_assign_folds_reraises_on_a_broken_invariant(self) -> None:
        """assign_folds re-checks its own guarantee before returning."""
        frame = _grid_frame(6, 6)
        manifest = assign_folds(frame, strategy="country", k=2)
        tampered = type(manifest)(
            strategy=manifest.strategy, k=manifest.k, seed=manifest.seed,
            fold_of={**manifest.fold_of, next(iter(manifest.fold_of)): 99},
            block_of=manifest.block_of,
        )
        assert tampered.blocks_spanning_folds(), "tampering must be detectable"
        _ = ContractViolationError


class TestStratifiedAllocation:
    """Block integrity and block ASSIGNMENT are independent degrees of freedom.

    Keeping blocks atomic is non-negotiable and settled. *Which* fold a whole block joins is a
    free choice, and choosing it by size alone concentrates a region's classes in a few folds
    as a pure artifact. MEASURED at S6: size-balanced allocation leaves 3 classes absent from
    a fold for no reason other than packing order (132, 141, 421); rarity-aware stratified
    allocation removes all 3 and reaches the theoretical floor of 14, which is the count of
    classes present in fewer than k=5 tiles and therefore unreachable under ANY allocation.
    """

    def _tile_classes(self) -> dict[str, set[int]]:
        path = project_root() / "reports/evaluation/tile_class_presence.json"
        if not path.is_file():
            pytest.skip("tile class presence not measured")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {t: set(v) for t, v in raw["tile_classes"].items()}

    def test_stratified_keeps_blocks_atomic(self) -> None:
        """The leakage guarantee must be identical — that is the whole point."""
        frame = pd.concat([_grid_frame(4, 4, f"T3{i}AAA") for i in range(6)], ignore_index=True)
        contents = {f"T3{i}AAA": {111, 211 + i} for i in range(6)}
        manifest = assign_folds_stratified(frame, contents, strategy="s2_tile", k=3)
        assert manifest.blocks_spanning_folds() == []
        assert adjacent_pairs_spanning_folds(frame, manifest) == []

    def test_stratified_spreads_a_class_across_folds(self) -> None:
        """A class in >= k blocks should reach every fold under rarity-aware allocation."""
        frame = pd.concat([_grid_frame(3, 3, f"T3{i}AAA") for i in range(6)], ignore_index=True)
        # class 999001 is rare but present in 3 blocks; k=3 so it CAN reach every fold
        contents = {f"T3{i}AAA": ({111} | ({999001} if i < 3 else set())) for i in range(6)}
        manifest = assign_folds_stratified(frame, contents, strategy="s2_tile", k=3)
        per_fold: dict[int, set[int]] = {f: set() for f in range(3)}
        for block, fold in {
            b: manifest.fold_of[p]
            for p, b in manifest.block_of.items()
        }.items():
            per_fold[fold] |= contents[block]
        assert all(999001 in per_fold[f] for f in range(3)), (
            "a class present in k blocks must be placeable in every fold"
        )

    def test_stratified_is_deterministic(self) -> None:
        frame = pd.concat([_grid_frame(3, 3, f"T3{i}AAA") for i in range(6)], ignore_index=True)
        contents = {f"T3{i}AAA": {111, 211 + i} for i in range(6)}
        a = assign_folds_stratified(frame, contents, strategy="s2_tile", k=3, seed=1337)
        b = assign_folds_stratified(frame, contents, strategy="s2_tile", k=3, seed=1337)
        assert a.fold_of == b.fold_of

    def test_final_split_reaches_the_irreducible_floor(self) -> None:
        """On the real data: zero allocation artifacts remain."""
        path = project_root() / "reports/evaluation/allocation_comparison.json"
        if not path.is_file():
            pytest.skip("allocation comparison not run")
        raw = json.loads(path.read_text(encoding="utf-8"))
        strat = raw["stratified (rarity-aware)"]
        assert strat["absent_artifact"] == [], (
            f"stratified allocation left removable absences: {strat['absent_artifact']}"
        )
        assert strat["adjacent_pairs_split"] == 0, "leakage guarantee must be unchanged"
        assert sorted(strat["absent_irreducible"]) == sorted(raw["theoretical_floor"])
