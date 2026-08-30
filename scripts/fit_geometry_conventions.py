"""S7 Part B — fit M2's conventions against GROUND-TRUTH maps and released answers.

The architecture requires connectivity, MMU, dilation radius and the area bin-boundary rule to
be **recovered from data, not guessed**. A wrong connectivity swings every counting answer, and
the failure is silent.

**Supervision.** S3 established that binary questions are comparator-form, which gives only
indirect supervision. MCQ questions give *direct* labels and are used instead:

- ``mcq|count`` — the correct option's integer **is** the true region count.
- ``mcq|area``  — the correct option's range **contains** the true coverage.
- ``binary|adjacency`` — yes/no supervision for the dilation sweep.

**Two obligations inherited from earlier stages, both honoured here:**

1. **S3 GR-2** deferred the area bin-boundary convention (``bin_boundary_rule``, still ``null``)
   to this stage, to be confirmed against computed ground truth rather than swept blindly.
2. **S6 GATE-2 propagation** requires per-class evaluation over each class's own valid fold
   set. Pooling a convention across folds that do not all contain the same classes would
   reintroduce exactly the averaging error S6 just removed. Every sweep here is therefore
   scored per class and aggregated only over classes, never over a pooled example soup.

Fitting uses the **training annotation split only** (CLAUDE.md §7); the loader enforces it.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from satquery.data.splits import load_manifest
from satquery.evaluation.forensics import iter_annotations
from satquery.geometry import GeometryParams, extract_regions
from satquery.taxonomy import load_synonyms, load_taxonomy
from satquery.utils.paths import project_root

STORE = "data/interim/reben/reference_maps"
FINAL_SPLIT = "data/processed/splits/FINAL_s2_tile_stratified_k5_seed1337.json"
TILE = re.compile(r"_(T\d{2}[A-Z]{3})_\d+_\d+$")
OPTLET = re.compile(r"(?:^|[,;]\s*|\s)([a-d])\)\s*(.+?)(?=(?:[,;]\s*|\s)[a-d]\)|$)")
RANGE = re.compile(r"([\d,\.]+)\s*to\s*([\d,\.]+)")
INT = re.compile(r"^\s*([\d,]+)\s*$")
PATCH_AREA_M2 = 1_440_000.0


@dataclass(frozen=True)
class Example:
    """One MCQ item with its ground-truth label recovered from the correct option."""

    patch_id: str
    class_name: str
    truth: float                 # count, or coverage-range lower bound
    hi: float = 0.0              # range upper bound for area
    unit: str = "count"


def load_map(root: Path, patch_id: str) -> np.ndarray | None:
    m = TILE.search(patch_id)
    if m is None:
        return None
    path = root / STORE / m.group(1) / f"{patch_id}.tif"
    if not path.is_file():
        return None
    with rasterio.open(path) as ds:
        return np.asarray(ds.read(1))


def collect(
    category: str, limit: int, row_groups: int,
    fold_of: dict[str, int] | None = None, k: int = 5,
) -> list[Example]:
    """Harvest MCQ examples whose correct option gives a direct label.

    **Stratified across folds.** Taking the first N matches drew them all from a single fold,
    which would fit a convention on one region's geography and violates the S6 GATE-2 rule that
    evaluation spans each class's own valid fold set. A per-fold quota fixes it.
    """
    syn = load_synonyms()
    out: list[Example] = []
    per_fold_quota = max(1, limit // k) if fold_of else limit
    fold_counts: collections.Counter[int] = collections.Counter()
    for frame in iter_annotations(
        ["patch_id", "input", "output", "type", "category"],
        splits=("train",), row_groups=range(row_groups),
    ):
        sub = frame[(frame.type == "mcq") & (frame.category == category)]
        for pid, q, ans in zip(sub.patch_id, sub.input, sub.output, strict=True):
            seg = q.split("?", 1)[-1] if "?" in q else q
            opts = {ll: t.strip().rstrip(".") for ll, t in OPTLET.findall(seg)}
            chosen = opts.get(str(ans).strip())
            if chosen is None:
                continue
            low = q.lower()
            hit = next((f for f in syn.forms if f in low), None)
            if hit is None:
                continue
            cls = syn.resolve(hit).canonical
            if fold_of is not None:
                f = fold_of.get(str(pid))
                if f is None or fold_counts[f] >= per_fold_quota:
                    continue
                fold_counts[f] += 1
            if category == "count":
                m = INT.match(chosen)
                if m:
                    out.append(Example(str(pid), cls, float(m.group(1).replace(",", ""))))
            else:
                m = RANGE.search(chosen)
                if m:
                    lo = float(m.group(1).replace(",", ""))
                    hi = float(m.group(2).replace(",", ""))
                    unit = "pct" if "%" in chosen else "m2"
                    if unit == "m2":
                        lo, hi = 100.0 * lo / PATCH_AREA_M2, 100.0 * hi / PATCH_AREA_M2
                    out.append(Example(str(pid), cls, lo, hi, "pct"))
            if len(out) >= limit:
                return out
    return out


def per_class_accuracy(hits: dict[str, list[bool]]) -> tuple[float, int, dict[str, float]]:
    """Mean of per-class accuracies — NOT a pooled rate (S6 GATE-2 propagation).

    Pooling would weight a class by how often it happens to be asked about, which is exactly
    the averaging error S6 removed at the fold level.
    """
    per_class = {c: sum(v) / len(v) for c, v in hits.items() if v}
    if not per_class:
        return 0.0, 0, {}
    return sum(per_class.values()) / len(per_class), sum(len(v) for v in hits.values()), per_class


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1400)
    parser.add_argument("--row-groups", type=int, default=8)
    args = parser.parse_args(argv)

    root = project_root()
    tax = load_taxonomy()
    manifest = load_manifest(root / FINAL_SPLIT)
    print("Fitting on the TRAINING annotation split only (CLAUDE.md §7).")
    print("Per-class scoring over each class's own valid fold set (S6 GATE-2 propagation).\n")

    results: dict[str, Any] = {}

    # ---------------------------------------------------------------- 1. connectivity + MMU
    counts = collect("count", args.limit, args.row_groups, manifest.fold_of)
    print(f"### mcq|count examples with a direct integer label: {len(counts):,}")
    cache: dict[str, np.ndarray] = {}
    for ex in counts:
        if ex.patch_id not in cache:
            m = load_map(root, ex.patch_id)
            if m is not None:
                cache[ex.patch_id] = m
    usable = [e for e in counts if e.patch_id in cache]
    folds = {e.patch_id: manifest.fold_of.get(e.patch_id) for e in usable}
    print(f"    with a reference map on disk: {len(usable):,}")
    print(f"    distinct classes: {len({e.class_name for e in usable})}   "
          f"folds represented: {sorted({f for f in folds.values() if f is not None})}\n")

    print(f"{'conn':>5} {'MMU':>5} {'per-class acc':>14} {'pooled acc':>12} {'classes':>8}")
    grid = []
    for conn in (4, 8):
        for mmu in (0, 1, 2, 4, 8, 16, 32):
            p = GeometryParams(connectivity=conn, min_mapping_unit_px=mmu,
                               opening_kernel_px=0, adjacency_dilation_px=1)
            hits: dict[str, list[bool]] = collections.defaultdict(list)
            pooled = []
            for ex in usable:
                try:
                    r = extract_regions(cache[ex.patch_id], ex.class_name, "c19", tax, p)
                except Exception:
                    continue
                ok = len(r) == int(ex.truth)
                hits[ex.class_name].append(ok)
                pooled.append(ok)
            acc, n, per_cls = per_class_accuracy(hits)
            pool = sum(pooled) / len(pooled) if pooled else 0.0
            grid.append({"connectivity": conn, "mmu": mmu, "per_class_acc": round(acc, 4),
                         "pooled_acc": round(pool, 4), "n": n, "classes": len(per_cls)})
            print(f"{conn:>5} {mmu:>5} {100*acc:>13.2f}% {100*pool:>11.2f}% {len(per_cls):>8}")
    best = max(grid, key=lambda g: (g["per_class_acc"], -g["mmu"]))
    runner = max((g for g in grid if g["connectivity"] != best["connectivity"]),
                 key=lambda g: g["per_class_acc"])
    print(f"\n  BEST: connectivity={best['connectivity']} MMU={best['mmu']} "
          f"per-class acc={100*best['per_class_acc']:.2f}%")
    print(f"  margin over the other connectivity: "
          f"{100*(best['per_class_acc'] - runner['per_class_acc']):+.2f} pts")
    results["connectivity_mmu"] = {"grid": grid, "best": best, "runner_up": runner}

    # ---------------------------------------------------------------- 2. area bin boundary
    areas = collect("area", args.limit, args.row_groups, manifest.fold_of)
    for ex in areas:
        if ex.patch_id not in cache:
            m = load_map(root, ex.patch_id)
            if m is not None:
                cache[ex.patch_id] = m
    ausable = [e for e in areas if e.patch_id in cache]
    print(f"\n### mcq|area examples with a direct range label: {len(ausable):,}")
    p_best = GeometryParams(connectivity=best["connectivity"], min_mapping_unit_px=best["mmu"],
                            opening_kernel_px=0, adjacency_dilation_px=1)
    rules = {
        "inclusive_lower_exclusive_upper": lambda v, lo, hi: lo <= v < hi or (hi >= 100 and v >= lo),
        "inclusive_both": lambda v, lo, hi: lo <= v <= hi,
        "exclusive_lower_inclusive_upper": lambda v, lo, hi: lo < v <= hi or (lo <= 0 and v == 0),
    }
    print(f"{'rule':>36} {'per-class acc':>14} {'pooled':>10}")
    rule_rows = []
    for name, fn in rules.items():
        hits = collections.defaultdict(list)
        pooled = []
        for ex in ausable:
            try:
                r = extract_regions(cache[ex.patch_id], ex.class_name, "c19", tax, p_best)
            except Exception:
                continue
            ok = bool(fn(100.0 * r.coverage, ex.truth, ex.hi))
            hits[ex.class_name].append(ok); pooled.append(ok)
        acc, n, per_cls = per_class_accuracy(hits)
        pool = sum(pooled) / len(pooled) if pooled else 0.0
        rule_rows.append({"rule": name, "per_class_acc": round(acc, 4),
                          "pooled_acc": round(pool, 4), "n": n})
        print(f"{name:>36} {100*acc:>13.2f}% {100*pool:>9.2f}%")
    best_rule = max(rule_rows, key=lambda r: r["per_class_acc"])
    print(f"\n  BEST BOUNDARY RULE: {best_rule['rule']} "
          f"({100*best_rule['per_class_acc']:.2f}% per-class)")
    results["bin_boundary_rule"] = {"rows": rule_rows, "best": best_rule}

    # ---------------------------------------------------------------- 3. dilation radius
    print("\n### binary|adjacency — dilation radius sweep")
    adj: list[tuple[str, str, str, str]] = []
    adj_folds: collections.Counter[int] = collections.Counter()
    syn = load_synonyms()
    for frame in iter_annotations(["patch_id", "input", "output", "type", "category"],
                                  splits=("train",), row_groups=range(args.row_groups)):
        sub = frame[(frame.type == "binary") & (frame.category == "adjacency")]
        for pid, q, ans in zip(sub.patch_id, sub.input, sub.output, strict=True):
            low = q.lower()
            found = [f for f in syn.forms if f in low]
            names = list(dict.fromkeys(syn.resolve(f).canonical for f in found))
            f = manifest.fold_of.get(str(pid))
            if len(names) == 2 and str(pid) in cache and f is not None                     and adj_folds[f] < max(1, args.limit // 5):
                adj_folds[f] += 1
                adj.append((str(pid), names[0], names[1], str(ans)))
            if len(adj) >= args.limit:
                break
        if len(adj) >= args.limit:
            break
    print(f"    usable adjacency items (2 classes, map cached): {len(adj):,}")
    from satquery.geometry import compute_adjacency
    print(f"{'k':>3} {'per-class acc':>14} {'pooled':>10}")
    krows = []
    for k in (0, 1, 2, 3, 5):
        p = GeometryParams(connectivity=best["connectivity"], min_mapping_unit_px=best["mmu"],
                           opening_kernel_px=0, adjacency_dilation_px=k)
        hits = collections.defaultdict(list); pooled = []
        for pid, a, b, ans in adj:
            try:
                res = compute_adjacency(cache[pid], a, b, "c19", tax, p)
            except Exception:
                continue
            ok = (res.adjacent and ans == "yes") or (not res.adjacent and ans == "no")
            hits[f"{a}|{b}"].append(ok); pooled.append(ok)
        acc, n, per_cls = per_class_accuracy(hits)
        pool = sum(pooled)/len(pooled) if pooled else 0.0
        krows.append({"k": k, "per_class_acc": round(acc, 4), "pooled_acc": round(pool, 4), "n": n})
        print(f"{k:>3} {100*acc:>13.2f}% {100*pool:>9.2f}%")
    best_k = max(krows, key=lambda r: r["per_class_acc"])
    print(f"\n  BEST DILATION RADIUS: k={best_k['k']} "
          f"({100*best_k['per_class_acc']:.2f}% per-class)")
    results["dilation"] = {"rows": krows, "best": best_k}

    out = root / "reports/experiments/geometry_conventions.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {out}")
    _ = random, sys
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
