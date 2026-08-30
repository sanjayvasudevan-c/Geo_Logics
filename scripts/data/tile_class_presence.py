"""Per-TILE CORINE class presence — the diagnostic that settles reducibility.

A class present in fewer than k tiles CANNOT appear in all k folds under any allocation,
because tiles are atomic. That is an irreducible absence. A class present in >= k tiles that
is still missing from a fold is an ALLOCATION artifact and can be fixed by assigning blocks
better. Distinguishing the two is what tells us whether Option A is forced or merely convenient.
"""
from __future__ import annotations

import collections
import json
import random
import re

import numpy as np
import rasterio

from satquery.taxonomy import load_taxonomy
from satquery.utils.paths import project_root

PER_TILE = 140
SEED = 1337
TILE = re.compile(r"_(T\d{2}[A-Z]{3})_\d+_\d+$")

def main() -> int:
    root = project_root()
    store = root / "data/interim/reben/reference_maps"
    import pandas as pd
    geo = pd.read_parquet(root/"data/processed/geography_train.parquet")
    tax = load_taxonomy()
    by_tile = collections.defaultdict(list)
    for pid, t in zip(geo.patch_id, geo.tile, strict=True):
        by_tile[str(t)].append(str(pid))
    rng = random.Random(SEED)
    tile_classes: dict[str, set[int]] = {}
    for tile in sorted(by_tile):
        pick = rng.sample(by_tile[tile], min(PER_TILE, len(by_tile[tile])))
        seen: set[int] = set()
        for pid in pick:
            p = store / tile / f"{pid}.tif"
            if not p.is_file():
                continue
            with rasterio.open(p) as ds:
                seen.update(int(v) for v in np.unique(ds.read(1)))
        tile_classes[tile] = seen
    print(f"tiles scanned: {len(tile_classes)}  ({PER_TILE} maps each, seed {SEED})\n")

    codes = sorted(c.code for c in tax.classes)
    tiles_with = {c: sum(1 for s in tile_classes.values() if c in s) for c in codes}
    print(f"{'code':>5} {'name':46s} {'tiles':>6} {'verdict'}")
    irreducible, reducible = [], []
    for c in codes:
        n = tiles_with[c]
        if n == 0:
            verdict = "ABSENT FROM CORPUS"; irreducible.append(c)
        elif n < 5:
            verdict = f"IRREDUCIBLE (only {n} tile(s) < k=5)"; irreducible.append(c)
        else:
            verdict = "reducible by allocation"
            reducible.append(c)
        print(f"{c:>5} {tax.by_code(c).name[:46]:46s} {n:>6} {verdict}")
    print()
    print(f"IRREDUCIBLE (cannot reach 5 folds under ANY allocation): {len(irreducible)}")
    print(f"   {irreducible}")
    print(f"REDUCIBLE (>=5 tiles; absence is an allocation artifact): {len(reducible)}")
    out = root/"reports/evaluation/tile_class_presence.json"
    out.write_text(json.dumps({
        "per_tile": PER_TILE, "seed": SEED,
        "tiles_containing_class": {str(k): v for k, v in tiles_with.items()},
        "irreducible": irreducible, "reducible": reducible,
        "tile_classes": {t: sorted(s) for t, s in tile_classes.items()},
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
