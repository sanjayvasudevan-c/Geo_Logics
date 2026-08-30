"""S4 — empirical CORINE L3 inventory + L3->19 mapping derivation.

Two questions the taxonomy layer cannot be built without:
  1. WHICH L3 codes actually occur? (CLAUDE.md says 44; S2's biased probe found 43 + 999)
  2. What is the L3 -> 19-class mapping? Derived from co-occurrence between each map's L3
     codes and that patch's official 19-class multi-label, not from memory.

Sampling is stratified across all 54 S2 tiles so the inventory is not geographically biased
the way S2's archive-order probe was.
"""
from __future__ import annotations

import collections
import json
import random

import numpy as np
import pandas as pd
import rasterio

from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/t01_class_inventory.json"
PER_TILE = 320
SEED = 1337

def main() -> int:
    root = project_root()
    store = root / "data/interim/reben/reference_maps"
    md = pd.read_parquet(root / "data/raw/reben/metadata.parquet", columns=["patch_id", "labels"])
    labels_by_patch = dict(zip(md.patch_id, md.labels, strict=True))
    print(f"metadata labels available for {len(labels_by_patch):,} patches")

    rng = random.Random(SEED)
    tiles = sorted(p for p in store.iterdir() if p.is_dir())
    print(f"tile shards: {len(tiles)}")

    px = collections.Counter()          # code -> pixel count
    patches = collections.Counter()     # code -> patch count
    cooc = collections.defaultdict(collections.Counter)  # code -> Counter(19-label)
    code_patch_with_labels = collections.Counter()
    scanned = 0
    no_label = 0

    for tile in tiles:
        files = sorted(tile.glob("*.tif"))
        pick = files if len(files) <= PER_TILE else rng.sample(files, PER_TILE)
        for f in pick:
            with rasterio.open(f) as ds:
                arr = ds.read(1)
            # numpy.unique is ~an order of magnitude faster here than pandas value_counts;
            # the first attempt at this scan timed out at 700/tile because of that.
            vals, counts = np.unique(arr, return_counts=True)
            codes = {int(v) for v in vals}
            for v, c in zip(vals, counts, strict=True):
                px[int(v)] += int(c)
            for v in codes:
                patches[v] += 1
            lab = labels_by_patch.get(f.stem)
            if lab is None:
                no_label += 1
            else:
                for v in codes:
                    code_patch_with_labels[v] += 1
                    cooc[v].update(lab)
            scanned += 1

    print(f"\nscanned {scanned:,} maps across {len(tiles)} tiles "
          f"({no_label:,} had no metadata labels — the snow/cloud-filtered patches)\n")
    print(f"### DISTINCT PIXEL VALUES FOUND: {len(px)} ###")
    total_px = sum(px.values())
    print(f"{'code':>6} {'pixel share %':>14} {'patches':>10} {'% of patches':>13}")
    for code in sorted(px):
        print(f"{code:>6} {100*px[code]/total_px:>14.5f} {patches[code]:>10,} "
              f"{100*patches[code]/scanned:>12.3f}%")

    print("\n### L3 -> 19-CLASS DERIVATION (co-occurrence, top label per code) ###")
    mapping = {}
    for code in sorted(cooc):
        n = code_patch_with_labels[code]
        top = cooc[code].most_common(3)
        best, best_n = top[0]
        conf = best_n / n if n else 0.0
        mapping[code] = {"label": best, "confidence": round(conf, 4), "support": n,
                         "runners_up": [(l, round(k/n, 3)) for l, k in top[1:]]}
        flag = "" if conf >= 0.98 else ("  <-- AMBIGUOUS" if conf < 0.90 else "  <-- check")
        print(f"  {code:>4} -> {best[:52]:52s} conf={conf:6.3f} n={n:>7,}{flag}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "scanned": scanned, "per_tile": PER_TILE, "seed": SEED, "tiles": len(tiles),
        "patches_without_labels": no_label,
        "distinct_values": sorted(px),
        "pixel_counts": {str(k): v for k, v in sorted(px.items())},
        "patch_counts": {str(k): v for k, v in sorted(patches.items())},
        "l3_to_19_derived": {str(k): v for k, v in mapping.items()},
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
