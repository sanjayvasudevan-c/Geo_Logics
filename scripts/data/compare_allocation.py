"""Does stratified block-to-fold allocation reduce the class-absence count?

Compares size-balanced allocation (the S6 default) against rarity-aware stratified allocation.
Both keep every block atomic, so the leakage guarantee is identical; only the assignment of
whole blocks to folds differs.
"""
from __future__ import annotations

import json

import pandas as pd

from satquery.data.splits import (
    adjacent_pairs_spanning_folds,
    all_adjacent_pairs,
    assign_folds,
    assign_folds_stratified,
)
from satquery.taxonomy import load_taxonomy
from satquery.utils.paths import project_root


def coverage(
    fold_of: dict[str, int],
    geo: pd.DataFrame,
    tile_classes: dict[str, set[int]],
    k: int,
) -> dict[int, set[int]]:
    """Classes present per fold, derived from which tiles landed where."""
    per_fold = {f: set() for f in range(k)}
    tile_fold = {}
    for pid, tile in zip(geo.patch_id, geo.tile, strict=True):
        f = fold_of.get(str(pid))
        if f is not None:
            tile_fold[str(tile)] = f
    for tile, f in tile_fold.items():
        per_fold[f] |= set(tile_classes.get(tile, []))
    return per_fold

def main() -> int:
    root = project_root()
    geo = pd.read_parquet(root/"data/processed/geography_train.parquet")
    tax = load_taxonomy()
    pres = json.loads((root/"reports/evaluation/tile_class_presence.json").read_text("utf-8"))
    tile_classes = {t: set(v) for t, v in pres["tile_classes"].items()}
    irreducible = set(pres["irreducible"])
    codes = sorted(c.code for c in tax.classes)
    k = 5

    results = {}
    for name, manifest in (
        ("size_balanced (S6 default)", assign_folds(geo, strategy="s2_tile", k=k)),
        ("stratified (rarity-aware)",
         assign_folds_stratified(geo, tile_classes, strategy="s2_tile", k=k)),
    ):
        per_fold = coverage(manifest.fold_of, geo, tile_classes, k)
        absent = [c for c in codes if any(c not in per_fold[f] for f in range(k))]
        sizes = manifest.fold_sizes
        pairs = all_adjacent_pairs(geo)
        split = len(adjacent_pairs_spanning_folds(geo, manifest))
        bal = min(sizes.values())/max(sizes.values())
        print(f"=== {name} ===")
        print(f"  fold sizes      : {dict(sizes)}")
        print(f"  balance         : {bal:.3f}")
        print(f"  BINDING: touching pairs split: {split:,} of {pairs:,}")
        print(f"  classes absent from >=1 fold : {len(absent)}")
        print(f"     of which IRREDUCIBLE (<5 tiles): "
              f"{len([c for c in absent if c in irreducible])}")
        print(f"     of which ALLOCATION ARTIFACT   : "
              f"{len([c for c in absent if c not in irreducible])}"
              f"  {[c for c in absent if c not in irreducible]}")
        print()
        results[name] = {
            "fold_sizes": {str(a): b for a, b in sizes.items()},
            "balance": round(bal, 4), "adjacent_pairs_split": split,
            "classes_absent": absent,
            "absent_irreducible": [c for c in absent if c in irreducible],
            "absent_artifact": [c for c in absent if c not in irreducible],
        }
    print(f"theoretical floor (classes in <{k} tiles): {len(irreducible)}  {sorted(irreducible)}")
    results["theoretical_floor"] = sorted(irreducible)
    out = root/"reports/evaluation/allocation_comparison.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
