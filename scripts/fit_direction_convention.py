"""S7 ADDENDUM — fit the relative-position direction convention.

S7 fitted connectivity, MMU, opening kernel and adjacency dilation, but never the direction
rule. GATE 1 measured ``mcq|relative pos`` at 65.33% with **0% abstention**, so those are
genuinely wrong answers, and the single uncalibrated component in an otherwise calibrated M2.
This closes it with the same discipline as the other four: recovered from ground-truth maps and
released answers, on **train** only, scored per class-pair over each pair's own valid fold set.

Three conventions are fitted jointly, because they interact:

1. **Subject / reference orientation.** Instrumenting the templates found 81 stems, of which
   several *invert* which class is the subject — ``Using the <A> as the reference, ... the
   position of the <B>`` asks for **B relative to A**, and ``the spatial direction from <A> to
   <B>`` likewise points from A toward B. Reading the first-mentioned class as the subject is
   wrong for roughly a quarter of items. One boolean is fitted per template family.

2. **Reference point.** Which point stands for a multi-component class: the area-weighted
   centroid of the mask (the S7 default), the largest component's centroid, or the centre of
   the union bounding box.

3. **Diagonal band width.** ``diagonal_band_deg`` is the angular width of each diagonal sector.
   45 deg is the textbook equal-sector 8-way compass; 0 collapses to pure cardinals. The
   released answers are cardinal 81.24% of the time while cardinals are only ~62% of the
   offered options, so the generator's diagonal sectors are demonstrably narrower than 45 deg
   and the textbook rule cannot reproduce them.

Capacity check (D-S7-1's argument, reapplied): the fitted quantity is 4 booleans plus a
3-way choice plus one scalar, well under 10 bits, against >1,000 supervised labels. Fitting a
convention of this size on this much data cannot memorise the answers.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from dataclasses import dataclass
from math import comb
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from satquery.data.splits import load_manifest
from satquery.evaluation.forensics import iter_annotations
from satquery.evaluation.oracle import (
    OPTLET,
    _find_classes,
    option_direction,
    subject_is_second,
)
from satquery.geometry import GeometryParams, RegionSet, extract_regions
from satquery.geometry import quantise_bearing as quantise
from satquery.taxonomy import load_synonyms, load_taxonomy
from satquery.utils.paths import project_root

STORE = "data/interim/reben/reference_maps"
FINAL_SPLIT = "data/processed/splits/FINAL_s2_tile_stratified_k5_seed1337.json"
TILE = re.compile(r"_(T\d{2}[A-Z]{3})_\d+_\d+$")

CARDINALS = ("N", "E", "S", "W")
DIAGONALS = ("NE", "SE", "SW", "NW")
BEARING = {"N": 0.0, "NE": 45.0, "E": 90.0, "SE": 135.0,
           "S": 180.0, "SW": 225.0, "W": 270.0, "NW": 315.0}

#: Template families, matched against the question stem. Each gets one fitted boolean saying
#: whether the first-mentioned class is the subject or the reference.
FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ref_first", re.compile(
        r"^\s*(?:using|considering|relative to|in relation to|compared (?:to|with))\b"
        r"|as (?:the|a) reference", re.I)),
    ("from_to", re.compile(r"\bdirection from\b|\bspatial direction from\b", re.I)),
    ("between", re.compile(r"\bbetween\b", re.I)),
)
DEFAULT_FAMILY = "subject_first"
REFERENCE_RULES = ("mask_centroid", "largest_component", "bbox_centre")


def family_of(question: str) -> str:
    """Which orientation family a question stem belongs to. First match wins."""
    stem = question.split("?", 1)[0]
    for name, rx in FAMILIES:
        if rx.search(stem):
            return name
    return DEFAULT_FAMILY


def angular_gap(a: str, b: str) -> float:
    """Smallest angle between two compass directions, in degrees."""
    d = abs(BEARING[a] - BEARING[b]) % 360.0
    return min(d, 360.0 - d)


def reference_point(rs: RegionSet, rule: str) -> tuple[float, float] | None:
    """The single (row, col) point standing for a possibly multi-component class."""
    if not rs.regions:
        return None
    if rule == "largest_component":
        r = max(rs.regions, key=lambda x: x.area_px)
        return r.centroid
    if rule == "bbox_centre":
        r0 = min(r.bbox[0] for r in rs.regions)
        c0 = min(r.bbox[1] for r in rs.regions)
        r1 = max(r.bbox[2] for r in rs.regions)
        c1 = max(r.bbox[3] for r in rs.regions)
        return ((r0 + r1) / 2.0, (c0 + c1) / 2.0)
    total = sum(r.area_px for r in rs.regions)
    return (sum(r.centroid[0] * r.area_px for r in rs.regions) / total,
            sum(r.centroid[1] * r.area_px for r in rs.regions) / total)


@dataclass(frozen=True)
class Item:
    """One relative-position MCQ with its precomputed geometry under every reference rule."""

    patch_id: str
    question: str
    fold: int
    family: str
    pair: str
    truth_letter: str
    options: dict[str, str]              # letter -> compass, unparsable options dropped
    points: dict[str, tuple[float, float, float, float]]   # rule -> (ar, ac, br, bc)


def load_map(root: Path, patch_id: str) -> np.ndarray | None:
    m = TILE.search(patch_id)
    if m is None:
        return None
    p = root / STORE / m.group(1) / f"{patch_id}.tif"
    if not p.is_file():
        return None
    with rasterio.open(p) as ds:
        return np.asarray(ds.read(1))


def bearing(ar: float, ac: float, br: float, bc: float) -> float | None:
    """Bearing of A from B. Row increases downward, so North is decreasing row."""
    d_row, d_col = ar - br, ac - bc
    if d_row == 0.0 and d_col == 0.0:
        return None
    return float(np.degrees(np.arctan2(d_col, -d_row)) % 360.0)


def predict(item: Item, flip: bool, rule: str, band: float) -> tuple[str | None, bool]:
    """Predicted option letter under one convention cell, and whether it matched exactly."""
    ar, ac, br, bc = item.points[rule]
    if flip:
        ar, ac, br, bc = br, bc, ar, ac
    b = bearing(ar, ac, br, bc)
    if b is None:
        return None, False
    want = quantise(b, band)
    for letter, compass in item.options.items():
        if compass == want:
            return letter, True
    if not item.options:
        return None, False
    gaps = {ll: angular_gap(want, c) for ll, c in item.options.items()}
    best = min(gaps.values())
    return sorted(ll for ll, g in gaps.items() if g == best)[0], False


def mcnemar(
    items: list[Item], flips: dict[str, bool],
    x: tuple[str, float], y: tuple[str, float],
) -> tuple[int, int, float]:
    """Exact-binomial McNemar test between two convention cells on paired items.

    Returns ``(b, c, p)`` where ``b`` counts items ``x`` gets right and ``y`` wrong. Two cells
    that differ by tenths of a point are not separable, and saying so is the honest result.
    """
    b = c = 0
    for it in items:
        px = predict(it, flips.get(it.family, False), x[0], x[1])[0] == it.truth_letter
        py = predict(it, flips.get(it.family, False), y[0], y[1])[0] == it.truth_letter
        b += int(px and not py)
        c += int(py and not px)
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    return b, c, min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)


def per_pair_accuracy(hits: dict[str, list[bool]]) -> tuple[float, int, int]:
    """Mean of per-class-pair accuracies, NOT a pooled rate (S6 GATE-2 propagation)."""
    per = {c: sum(v) / len(v) for c, v in hits.items() if v}
    if not per:
        return 0.0, 0, 0
    return sum(per.values()) / len(per), sum(len(v) for v in hits.values()), len(per)


def collect(root: Path, limit: int, row_groups: int, fold_of: dict[str, int], k: int = 5
            ) -> tuple[list[Item], collections.Counter[str]]:
    """Harvest train items with a per-fold quota, precomputing geometry once per item."""
    tax, syn = load_taxonomy(), load_synonyms()
    params = GeometryParams(connectivity=4, min_mapping_unit_px=0,
                            opening_kernel_px=0, adjacency_dilation_px=1)
    skips: collections.Counter[str] = collections.Counter()
    quota = max(1, limit // k)
    fold_counts: collections.Counter[int] = collections.Counter()
    out: list[Item] = []
    cache: dict[str, np.ndarray] = {}
    for frame in iter_annotations(
        ["patch_id", "input", "output", "type", "category"],
        splits=("train",), row_groups=range(row_groups),
    ):
        sub = frame[(frame.type == "mcq") & (frame.category == "relative pos")]
        for pid, q, ans in zip(sub.patch_id, sub.input, sub.output, strict=True):
            pid, q, ans = str(pid), str(q), str(ans).strip()
            fold = fold_of.get(pid)
            if fold is None:
                skips["patch not in split manifest"] += 1
                continue
            if fold_counts[fold] >= quota:
                continue
            classes = _find_classes(q, syn)
            if len(classes) != 2:
                skips[f"resolved {len(classes)} classes, need exactly 2"] += 1
                continue
            seg = q.split("?", 1)[-1] if "?" in q else q
            raw = {ll: t.strip().rstrip(".") for ll, t in OPTLET.findall(seg)}
            if len(raw) != 4:
                skips[f"parsed {len(raw)} options, need 4"] += 1
                continue
            opts = {ll: d for ll, t in raw.items() if (d := option_direction(t)) is not None}
            if ans not in opts:
                skips["correct option is not a direction"] += 1
                continue
            if pid not in cache:
                m = load_map(root, pid)
                if m is None:
                    skips["no reference map on disk"] += 1
                    continue
                cache[pid] = m
            try:
                ra = extract_regions(cache[pid], classes[0], "c19", tax, params)
                rb = extract_regions(cache[pid], classes[1], "c19", tax, params)
            except Exception:
                skips["taxonomy/geometry error"] += 1
                continue
            pts: dict[str, tuple[float, float, float, float]] = {}
            for rule in REFERENCE_RULES:
                pa, pb = reference_point(ra, rule), reference_point(rb, rule)
                if pa is None or pb is None:
                    break
                pts[rule] = (pa[0], pa[1], pb[0], pb[1])
            if len(pts) != len(REFERENCE_RULES):
                skips["one class absent from the map"] += 1
                continue
            fold_counts[fold] += 1
            out.append(Item(pid, q, fold, family_of(q), "|".join(sorted(classes)),
                            ans, opts, pts))
            if len(out) >= limit:
                return out, skips
    return out, skips


def score(items: list[Item], flips: dict[str, bool], rule: str, band: float
          ) -> tuple[float, float, int, int]:
    """Per-pair accuracy, pooled accuracy, n, and exact-match count for one cell."""
    hits: dict[str, list[bool]] = collections.defaultdict(list)
    pooled, exact = [], 0
    for it in items:
        letter, was_exact = predict(it, flips.get(it.family, False), rule, band)
        ok = letter == it.truth_letter
        hits[it.pair].append(ok)
        pooled.append(ok)
        exact += int(was_exact)
    acc, n, _ = per_pair_accuracy(hits)
    return acc, (sum(pooled) / len(pooled) if pooled else 0.0), n, exact


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--row-groups", type=int, default=10)
    args = ap.parse_args(argv)

    root = project_root()
    manifest = load_manifest(root / FINAL_SPLIT)
    print("Fitting on the TRAINING annotation split only (CLAUDE.md §7).")
    print("Per-class-pair scoring over each pair's own valid fold set (S6 GATE-2).\n")

    items, skips = collect(root, args.limit, args.row_groups, manifest.fold_of)
    print(f"### usable mcq|relative pos items: {len(items):,}")
    print(f"    folds represented : {sorted({i.fold for i in items})}")
    print(f"    distinct class-pairs: {len({i.pair for i in items})}")
    fam = collections.Counter(i.family for i in items)
    for f, c in fam.most_common():
        print(f"    family {f:<15} {c:>5,}  ({100*c/len(items):5.2f}%)")
    if skips:
        print("    skipped:")
        for r, c in skips.most_common():
            print(f"      {c:>5,}  {r}")
    print()

    results: dict[str, Any] = {"n": len(items), "families": dict(fam), "skips": dict(skips)}

    # ------------------------------------------------------- 1. orientation, per family
    # Fitted independently per family under the S7 baseline geometry, so the effect is
    # attributable to orientation alone rather than confounded with the band sweep.
    print("### 1. SUBJECT/REFERENCE ORIENTATION — per template family, textbook 45 deg band")
    print(f"{'family':<16} {'n':>6} {'as-written':>12} {'flipped':>10} {'delta':>9}  verdict")
    flips: dict[str, bool] = {}
    orient_rows = []
    for f in list(fam):
        sub = [i for i in items if i.family == f]
        a, _, _, _ = score(sub, {f: False}, "mask_centroid", 45.0)
        b, _, _, _ = score(sub, {f: True}, "mask_centroid", 45.0)
        flips[f] = b > a
        orient_rows.append({"family": f, "n": len(sub), "as_written": round(a, 4),
                            "flipped": round(b, 4), "flip": b > a})
        print(f"{f:<16} {len(sub):>6,} {100*a:>11.2f}% {100*b:>9.2f}% "
              f"{100*(b-a):>+8.2f}  {'FLIP' if b > a else 'keep as written'}")
    # ANTI-DRIFT: what this sweep just fitted must be what oracle.subject_is_second actually
    # ships. Without this, the fitted convention and the deployed parser could diverge silently
    # and every number below would describe a rule the system does not use.
    disagree = [i.patch_id for i in items
                if subject_is_second(i.question) != flips.get(i.family, False)]
    print(f"\n  anti-drift check vs oracle.subject_is_second(): "
          f"{len(items) - len(disagree):,}/{len(items):,} agree", end="")
    if disagree:
        print(f"  *** {len(disagree)} DISAGREE — the shipped parser does not implement the "
              f"fitted convention ***")
    else:
        print("  (the shipped parser implements exactly this convention)")
    results["orientation"] = {"rows": orient_rows, "fitted": dict(flips),
                              "shipped_parser_disagreements": len(disagree)}
    print()

    # ------------------------------------------------------- 2. reference point x band
    print("### 2. REFERENCE POINT x DIAGONAL BAND  (per-pair accuracy)")
    bands = [float(b) for b in range(0, 95, 5)]
    print(f"{'band':>6} " + " ".join(f"{r:>18}" for r in REFERENCE_RULES))
    grid = []
    for band in bands:
        cells = []
        for rule in REFERENCE_RULES:
            acc, pool, n, exact = score(items, flips, rule, band)
            grid.append({"band_deg": band, "rule": rule, "per_pair_acc": round(acc, 4),
                         "pooled_acc": round(pool, 4), "n": n,
                         "exact_match_rate": round(exact / max(n, 1), 4)})
            cells.append(f"{100*acc:>17.2f}%")
        print(f"{band:>6.0f} " + " ".join(cells))
    # Refine EVERY rule on a 1-degree grid, so the rules are compared each at its own best
    # band rather than on a coarse grid that may favour one arbitrarily.
    print("\n### 2b. 1-DEGREE REFINEMENT, each rule at its own optimum")
    fine: dict[str, list[dict[str, Any]]] = {}
    rule_best: dict[str, dict[str, Any]] = {}
    for rule in REFERENCE_RULES:
        rows = []
        for bi in range(0, 46):
            acc, pool, n, exact = score(items, flips, rule, float(bi))
            rows.append({"band_deg": float(bi), "per_pair_acc": round(acc, 4),
                         "pooled_acc": round(pool, 4)})
        fine[rule] = rows
        top = max(r["per_pair_acc"] for r in rows)
        # Plateau = every band within 0.5 pts of the peak. A single argmax on 1,600 items
        # is not resolvable to one degree; the plateau is the honest resolution.
        plate = [r["band_deg"] for r in rows if r["per_pair_acc"] >= top - 0.005]
        rule_best[rule] = {"peak_acc": top, "peak_deg": [r["band_deg"] for r in rows
                                                         if r["per_pair_acc"] == top],
                           "plateau_deg": [min(plate), max(plate)]}
        print(f"  {rule:<18} peak {100*top:.2f}% at {rule_best[rule]['peak_deg']}  "
              f"plateau (within 0.5 pts) = [{min(plate):.0f}, {max(plate):.0f}] deg")

    best_rule = max(REFERENCE_RULES, key=lambda r: rule_best[r]["peak_acc"])
    spread = (rule_best[best_rule]["peak_acc"]
              - min(rule_best[r]["peak_acc"] for r in REFERENCE_RULES))
    print(f"\n  best rule = {best_rule}; spread across rules at their own optima = "
          f"{100*spread:.2f} pts")

    # ---- independent evidence: match the OBSERVED diagonal rate, not just argmax ----------
    # The released correct answers are diagonal at a measured rate. A band that reproduces
    # that rate is corroborated by a statistic the accuracy sweep never optimised for.
    true_diag = sum(1 for i in items if i.options[i.truth_letter] in DIAGONALS) / len(items)
    print(f"\n### 2c. DISTRIBUTION MATCH — released answers are diagonal "
          f"{100*true_diag:.2f}% of the time")
    print(f"{'band':>6} {'predicted diagonal rate':>26} {'|error|':>9}")
    dist_rows = []
    for bi in range(0, 46, 2):
        pred_diag = 0
        for it in items:
            ar, ac, br, bc = it.points[best_rule]
            if flips.get(it.family, False):
                ar, ac, br, bc = br, bc, ar, ac
            bg = bearing(ar, ac, br, bc)
            if bg is not None and quantise(bg, float(bi)) in DIAGONALS:
                pred_diag += 1
        rate = pred_diag / len(items)
        dist_rows.append({"band_deg": float(bi), "pred_diagonal_rate": round(rate, 4)})
        if bi % 4 == 0:
            print(f"{bi:>6} {100*rate:>25.2f}% {100*abs(rate-true_diag):>8.2f}")
    dist_best = min(dist_rows, key=lambda r: abs(r["pred_diagonal_rate"] - true_diag))
    print(f"  band reproducing the observed diagonal rate: "
          f"{dist_best['band_deg']:.0f} deg "
          f"({100*dist_best['pred_diagonal_rate']:.2f}% vs {100*true_diag:.2f}% observed)")

    # ---- selection rule, stated in advance ------------------------------------------------
    # An argmax over cells that differ by tenths of a point on 2,500 items is not a
    # measurement. The rule applied here: a candidate supported by BOTH lines of evidence
    # (its accuracy plateau contains the distribution-matched band) is preferred over the bare
    # accuracy argmax UNLESS McNemar can actually separate them at p < 0.05.
    dm = dist_best["band_deg"]
    convergent = [r for r in REFERENCE_RULES
                  if rule_best[r]["plateau_deg"][0] <= dm <= rule_best[r]["plateau_deg"][1]]
    argmax_cell = (best_rule, float(rule_best[best_rule]["peak_deg"][0]))
    print("\n### 2d. SELECTION")
    print(f"  accuracy argmax      : {argmax_cell[0]} @ {argmax_cell[1]:.0f} deg")
    print(f"  convergent candidates: "
          f"{[f'{r} @ {dm:.0f}' for r in convergent] or 'none'}")
    if convergent:
        cand = max(convergent, key=lambda r: score(items, flips, r, dm)[0])
        cand_cell = (cand, dm)
        b, c, p = mcnemar(items, flips, argmax_cell, cand_cell)
        print(f"  McNemar argmax vs convergent: discordant {b}/{c}, exact binomial p = {p:.3f}")
        if p < 0.05:
            chosen_rule, chosen_band = argmax_cell
            print(f"  -> argmax is SEPARABLE; adopting {chosen_rule} @ {chosen_band:.0f} deg.")
        else:
            chosen_rule, chosen_band = cand_cell
            print(f"  -> NOT separable, so accuracy does not decide. Adopting the convergent "
                  f"candidate {chosen_rule} @ {chosen_band:.0f} deg, which is supported by an "
                  f"independent statistic the sweep never optimised for.")
    else:
        chosen_rule, chosen_band = argmax_cell
        print("  -> no convergent candidate; adopting the accuracy argmax, "
              "UNDER-DETERMINED.")
    best = {"rule": chosen_rule, "band_deg": chosen_band,
            "per_pair_acc": score(items, flips, chosen_rule, chosen_band)[0]}
    results["grid"] = {"coarse": grid, "fine": fine, "rule_best": rule_best,
                       "accuracy_argmax": list(argmax_cell), "rule_spread": round(spread, 4),
                       "true_diagonal_rate": round(true_diag, 4), "dist_rows": dist_rows,
                       "dist_matched_deg": dm, "convergent_rules": convergent,
                       "chosen_rule": chosen_rule, "chosen_band_deg": chosen_band}

    # ---- how much of the rule choice is even decidable? ----------------------------------
    print("\n### 2e. IS THE REFERENCE-POINT RULE DECIDABLE AT ALL?")
    equiv: dict[str, dict[str, int]] = {}
    for i, ra in enumerate(REFERENCE_RULES):
        for rb in REFERENCE_RULES[i + 1:]:
            pt_diff = sum(1 for it in items if it.points[ra] != it.points[rb])
            ans_diff = sum(
                1 for it in items
                if predict(it, flips.get(it.family, False), ra, chosen_band)[0]
                != predict(it, flips.get(it.family, False), rb, chosen_band)[0]
            )
            equiv[f"{ra} vs {rb}"] = {"reference_point_differs": pt_diff,
                                      "predicted_answer_differs": ans_diff}
            print(f"  {ra:<18} vs {rb:<18} point differs {pt_diff:>5,}/{len(items):,}  "
                  f"-> ANSWER differs {ans_diff:>5,}")
    results["rule_decidability"] = equiv

    # ------------------------------------------------------- 3. baseline vs fitted
    base_acc, base_pool, _, base_exact = score(items, {}, "mask_centroid", 45.0)
    fit_acc, fit_pool, n, fit_exact = score(items, flips, best["rule"], chosen_band)
    print("\n### 3. TRAIN-SPLIT BEFORE / AFTER")
    print(f"  S7 baseline (no flips, mask centroid, 45 deg): "
          f"per-pair {100*base_acc:.2f}%  pooled {100*base_pool:.2f}%  "
          f"exact-match {100*base_exact/n:.1f}%")
    print(f"  fitted convention                            : "
          f"per-pair {100*fit_acc:.2f}%  pooled {100*fit_pool:.2f}%  "
          f"exact-match {100*fit_exact/n:.1f}%")
    print(f"  delta                                        : "
          f"per-pair {100*(fit_acc-base_acc):+.2f}  pooled {100*(fit_pool-base_pool):+.2f}")
    results["before_after"] = {
        "baseline": {"per_pair_acc": round(base_acc, 4), "pooled_acc": round(base_pool, 4)},
        "fitted": {"per_pair_acc": round(fit_acc, 4), "pooled_acc": round(fit_pool, 4)},
    }

    # ---- where the RESIDUAL error actually is, so it is not guessed at downstream ----------
    print("\n### 3b. RESIDUAL ERROR BY TEMPLATE FAMILY, under the fitted convention")
    print(f"{'family':<16} {'n':>6} {'accuracy':>10} {'errors':>8} {'share of all errors':>21}")
    total_err = sum(
        1 for it in items
        if predict(it, flips.get(it.family, False), best["rule"], chosen_band)[0]
        != it.truth_letter
    )
    resid = []
    for fname in sorted(fam, key=lambda x: -fam[x]):
        sub = [i for i in items if i.family == fname]
        err = sum(1 for it in sub
                  if predict(it, flips.get(fname, False), best["rule"], chosen_band)[0]
                  != it.truth_letter)
        resid.append({"family": fname, "n": len(sub), "errors": err,
                      "accuracy": round(1 - err / len(sub), 4),
                      "share_of_errors": round(err / total_err, 4) if total_err else 0.0})
        print(f"{fname:<16} {len(sub):>6,} {100*(1-err/len(sub)):>9.2f}% {err:>8,} "
              f"{100*err/max(total_err,1):>20.1f}%")
    worst = max(resid, key=lambda r: r["share_of_errors"])
    print(f"\n  largest remaining error source: `{worst['family']}` "
          f"({100*worst['share_of_errors']:.1f}% of all residual errors, "
          f"{100*worst['accuracy']:.2f}% accurate). NOT fitted further here.")
    results["residual_by_family"] = {"rows": resid, "total_errors": total_err,
                                     "worst": worst}

    # ------------------------------------------------------- 4. per-fold stability
    print("\n### 4. PER-FOLD STABILITY of the fitted convention")
    print(f"{'fold':>5} {'n':>6} {'baseline':>10} {'fitted':>9} {'delta':>8}")
    fold_rows = []
    for f in sorted({i.fold for i in items}):
        sub = [i for i in items if i.fold == f]
        a, _, _, _ = score(sub, {}, "mask_centroid", 45.0)
        c, _, _, _ = score(sub, flips, best["rule"], chosen_band)
        fold_rows.append({"fold": f, "n": len(sub), "baseline": round(a, 4),
                          "fitted": round(c, 4)})
        print(f"{f:>5} {len(sub):>6,} {100*a:>9.2f}% {100*c:>8.2f}% {100*(c-a):>+7.2f}")
    deltas = [r["fitted"] - r["baseline"] for r in fold_rows]
    print(f"\n  improves in {sum(1 for d in deltas if d > 0)}/{len(deltas)} folds; "
          f"min delta {100*min(deltas):+.2f}, max {100*max(deltas):+.2f}")
    results["per_fold"] = fold_rows

    results["fitted"] = {
        "direction_orientation_flip": dict(flips),
        "direction_reference_rule": best["rule"],
        "diagonal_band_deg": chosen_band,
    }
    out = root / "reports/experiments/direction_convention.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
