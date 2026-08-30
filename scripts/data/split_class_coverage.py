"""S6 HALT check — do rare CLC L3 classes survive in EVERY fold under geographic blocking?

STAGE_PROMPTS.md S6 halts if they do not. Reads the reference maps for a stratified sample of
each fold and records which of the 44 classes appear. A class absent from any fold is reported
loudly, not averaged away.
"""
from __future__ import annotations

import collections
import json
import random
import re

import numpy as np
import rasterio

from satquery.data.splits import load_manifest
from satquery.taxonomy import load_taxonomy
from satquery.utils.paths import project_root

PER_FOLD = 900
TILE = re.compile(r"_(T\d{2}[A-Z]{3})_\d+_\d+$")
SEED = 1337

def main() -> int:
    root = project_root()
    man = load_manifest(root / "data/processed/splits/s2_tile_k5_seed1337.json")
    tax = load_taxonomy()
    store = root / "data/interim/reben/reference_maps"
    by_fold = collections.defaultdict(list)
    for pid, fold in man.fold_of.items():
        by_fold[fold].append(pid)
    rng = random.Random(SEED)
    present = {f: collections.Counter() for f in sorted(by_fold)}
    scanned = {}
    for fold in sorted(by_fold):
        pick = rng.sample(by_fold[fold], min(PER_FOLD, len(by_fold[fold])))
        n = 0
        for pid in pick:
            # Construct the path from the tile in the patch id. Globbing 54 shards per patch
            # is what made the first attempt time out.
            m = TILE.search(pid)
            if m is None: continue
            p = store / m.group(1) / f"{pid}.tif"
            if not p.is_file(): continue
            with rasterio.open(p) as ds:
                vals = np.unique(ds.read(1))
            for v in vals:
                present[fold][int(v)] += 1
            n += 1
        scanned[fold] = n
        print(f"  fold {fold}: scanned {n:,} maps, {len(present[fold])} distinct classes")
    print()
    codes = sorted({c.code for c in tax.classes})
    missing_any = []
    print(f"{'code':>5} {'name':44s} " + " ".join(f"f{f}" for f in sorted(by_fold)))
    for code in codes:
        row = [present[f].get(code, 0) for f in sorted(by_fold)]
        flag = "  <-- ABSENT FROM A FOLD" if min(row) == 0 else ""
        if min(row) == 0: missing_any.append(code)
        print(f"{code:>5} {tax.by_code(code).name[:44]:44s} " +
              " ".join(f"{v:>5,}" for v in row) + flag)
    print()
    print(f"classes absent from >=1 fold: {len(missing_any)} -> {missing_any}")
    out = root / "reports/evaluation/fold_class_coverage.json"
    out.write_text(json.dumps({
        "per_fold_scanned": scanned, "seed": SEED, "per_fold": PER_FOLD,
        "class_patch_counts": {str(f): dict(present[f]) for f in present},
        "absent_from_some_fold": missing_any,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
