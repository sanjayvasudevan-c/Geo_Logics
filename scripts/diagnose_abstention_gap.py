"""CF-1 diagnostic — how much of Gate 1's abstention gap would Q1 actually close?

Gate 1's strict/attempted gap is **entirely parser abstention**, and it was produced by
``satquery/evaluation/oracle.py``'s S8 answer producer — **not** by the Q1 parser S9 built.
Those are different modules, so S9 did not close the gap by construction, and saying it did
would be a false close.

This script makes the size of that gap traceable instead of inferred. It does **two** things and
deliberately not a third:

1. Re-reads the recorded Gate 1 numbers and restates the gap exactly as measured.
2. For every item the S8 oracle **abstained** on, asks whether Q1 supplies the field the oracle
   was missing — a class name, a comparator, a threshold, or a second class for a pair.
3. It does **NOT** re-run or re-score Gate 1. Changing how a gate number was produced is a
   decision, not a cleanup, so the number here is a *recoverable-points estimate* and is
   labelled as such everywhere it appears.

Validation split only; the quarantined ``bench`` split is never touched.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import numpy as np
import rasterio

from satquery.config import load_config
from satquery.evaluation.forensics import iter_annotations
from satquery.evaluation.oracle import ParseFailure as OracleFailure
from satquery.evaluation.oracle import answer_question
from satquery.geometry import GeometryParams
from satquery.routing import ParseFailure as Q1Failure
from satquery.routing import QuerySpec, parse_query
from satquery.taxonomy import load_synonyms, load_taxonomy
from satquery.utils.paths import project_root

STORE = "data/interim/reben/reference_maps"
TILE = re.compile(r"_(T\d{2}[A-Z]{3})_\d+_\d+$")
GEOMETRIC = (
    "binary|presence", "binary|area", "binary|count", "binary|adjacency",
    "mcq|presence", "mcq|area", "mcq|count", "mcq|adjacency", "mcq|relative pos",
)

#: What each oracle abstention reason needs, and which QuerySpec field would supply it.
#: ``None`` marks a reason Q1 CANNOT fix — it is a geometry fact, not a parse failure.
NEEDS: tuple[tuple[re.Pattern[str], str | None], ...] = (
    (re.compile(r"no class name resolved"), "class_a"),
    (re.compile(r"no MCQ option resolved to a class"), "class_a"),
    (re.compile(r"needs two classes|yielded two classes"), "class_b"),
    (re.compile(r"no threshold"), "stated_value"),
    (re.compile(r"no comparator"), "comparator"),
    (re.compile(r"no numeric MCQ option|no range MCQ option"), "options"),
    (re.compile(r"no option parsed as a direction"), "options"),
    (re.compile(r"one class absent"), None),          # geometry, not parsing
    (re.compile(r"metadata task"), None),             # out of the oracle's scope by design
)


def _need(reason: str) -> tuple[str | None, bool]:
    """(required QuerySpec field, whether Q1 could ever fix it)."""
    for rx, field in NEEDS:
        if rx.search(reason):
            return field, field is not None
    return None, False


def load_map(root: Path, patch_id: str) -> np.ndarray | None:
    m = TILE.search(patch_id)
    if m is None:
        return None
    p = root / STORE / m.group(1) / f"{patch_id}.tif"
    if not p.is_file():
        return None
    with rasterio.open(p) as ds:
        return np.asarray(ds.read(1))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-task", type=int, default=300)
    ap.add_argument("--row-groups", type=int, default=26)
    args = ap.parse_args(argv)

    root = project_root()
    cfg = load_config()
    tax, syn = load_taxonomy(), load_synonyms()
    params = GeometryParams.from_config(cfg.m2, gsd_m=cfg.data.gsd_metres)

    gate = json.loads((root / "reports/evaluation/gate1_oracle.json").read_text("utf-8"))
    m = gate["_macro"]
    gap_pts = 100 * (m["oracle_attempted"] - m["oracle_strict"])
    print("=" * 78)
    print("CF-1 — GATE 1 ABSTENTION GAP, AS RECORDED")
    print("=" * 78)
    print(f"  MACRO strict     {100*m['oracle_strict']:.2f}%")
    print(f"  MACRO attempted  {100*m['oracle_attempted']:.2f}%")
    print(f"  GAP              {gap_pts:.2f} points  <- entirely abstention, not geometry")
    print("\n  Produced by evaluation/oracle.py (S8), NOT by routing/parser.py (S9).")
    print("  S9 did not change oracle.py, so this number is UNCHANGED by S9.\n")

    # --- collect the items the oracle abstained on, on the same protocol Gate 1 used --------
    print("Re-running the S8 oracle to recover its abstentions (validation split)...")
    items: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for frame in iter_annotations(
        ["patch_id", "input", "type", "category"],
        splits=("validation",), row_groups=range(args.row_groups),
    ):
        for pid, q, t, c in zip(frame.patch_id, frame.input, frame.type, frame.category,
                                strict=True):
            task = f"{t}|{c}"
            if task in GEOMETRIC and len(items[task]) < args.per_task:
                items[task].append((str(pid), str(q)))
        if all(len(items[t]) >= args.per_task for t in GEOMETRIC):
            break

    cache: dict[str, np.ndarray] = {}
    per_task: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"n": 0, "abstained": 0, "q1_fixes": 0, "unfixable": 0})
    reason_rows: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"n": 0, "fixed": 0})

    for task in GEOMETRIC:
        for pid, q in items[task]:
            if pid not in cache:
                mp = load_map(root, pid)
                if mp is None:
                    continue
                cache[pid] = mp
            rec = per_task[task]
            rec["n"] += 1
            got = answer_question(cache[pid], q, task, tax, syn, params, cfg.m2)
            if not isinstance(got, OracleFailure):
                continue
            rec["abstained"] += 1
            field, fixable = _need(got.reason)
            key = got.reason[:52]
            reason_rows[key]["n"] += 1
            if not fixable:
                rec["unfixable"] += 1
                continue
            spec = parse_query(q, syn)
            if isinstance(spec, Q1Failure):
                continue
            assert isinstance(spec, QuerySpec)
            value = getattr(spec, field) if field else None
            if value:
                rec["q1_fixes"] += 1
                reason_rows[key]["fixed"] += 1

    print("\n" + "=" * 78)
    print("WOULD Q1 SUPPLY WHAT THE ORACLE WAS MISSING?")
    print("=" * 78)
    print(f"{'task':<22}{'n':>6}{'abstain':>9}{'Q1 fixes':>10}{'unfixable':>11}{'rate':>8}")
    print("-" * 78)
    tot = {"n": 0, "abstained": 0, "q1_fixes": 0, "unfixable": 0}
    rows = []
    for task in GEOMETRIC:
        r = per_task[task]
        if not r["n"]:
            continue
        for k in tot:
            tot[k] += r[k]
        rate = r["q1_fixes"] / r["abstained"] if r["abstained"] else 0.0
        rows.append({"task": task, **r, "fix_rate": round(rate, 4)})
        print(f"{task:<22}{r['n']:>6}{r['abstained']:>9}{r['q1_fixes']:>10}"
              f"{r['unfixable']:>11}{100*rate:>7.1f}%")

    overall = tot["q1_fixes"] / tot["abstained"] if tot["abstained"] else 0.0
    print("-" * 78)
    print(f"{'TOTAL':<22}{tot['n']:>6}{tot['abstained']:>9}{tot['q1_fixes']:>10}"
          f"{tot['unfixable']:>11}{100*overall:>7.1f}%")

    print("\nBy oracle abstention reason:")
    print(f"  {'reason':<54}{'n':>6}{'Q1 fixes':>10}")
    for reason, r in sorted(reason_rows.items(), key=lambda kv: -kv[1]["n"]):
        print(f"  {reason:<54}{r['n']:>6}{r['fixed']:>10}")

    recoverable = gap_pts * overall
    print("\n" + "=" * 78)
    print("CF-1 — RECOVERABLE-POINTS ESTIMATE")
    print("=" * 78)
    print(f"  gap as measured at Gate 1            : {gap_pts:.2f} points")
    print(f"  share of abstentions Q1 can supply   : {100*overall:.1f}%")
    print(f"  -> ESTIMATED recoverable             : {recoverable:.2f} points")
    print(f"  -> ESTIMATED irreducible             : {gap_pts - recoverable:.2f} points")
    print("\n  THIS IS AN ESTIMATE, NOT A RE-MEASUREMENT. It says Q1 supplies the missing")
    print("  FIELD; it does not say the resulting answer is correct. Gate 1 has NOT been")
    print("  re-run and its recorded number is unchanged. Actually closing CF-1 means routing")
    print("  the oracle through Q1, which changes how a GATE number was produced — a decision,")
    print("  not a cleanup. Proposed home: S13.")

    out = root / "reports/experiments/cf1_abstention_diagnostic.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "gate1_gap_points": round(gap_pts, 4),
        "per_task": rows,
        "totals": tot,
        "q1_fix_rate": round(overall, 4),
        "estimated_recoverable_points": round(recoverable, 4),
        "estimated_irreducible_points": round(gap_pts - recoverable, 4),
        "by_reason": {k: v for k, v in reason_rows.items()},
        "caveat": "ESTIMATE ONLY. Q1 supplies the missing field; correctness of the resulting "
                  "answer was not scored. Gate 1 was NOT re-run.",
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
