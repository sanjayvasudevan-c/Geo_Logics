"""S3 item 5 — numeric conventions: area units, rounding granularity, count expression."""
from __future__ import annotations

import collections
import json
import re

import pandas as pd

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f05_numeric.json"
M2 = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:m2|m\^2|m²|square met(?:er|re)s?)", re.I)
PCT = re.compile(r"([\d]+(?:\.\d+)?)\s*%")
COMPARATOR = [
    ("at_least",      re.compile(r"at least|no less than|or more|minimum of", re.I)),
    ("at_most",       re.compile(r"at most|no more than|fewer than|less than|under", re.I)),
    ("more_than",     re.compile(r"more than|greater than|exceed|over ", re.I)),
    ("approximately", re.compile(r"approximately|about|roughly|around|close to", re.I)),
    ("exactly",       re.compile(r"exactly|precisely", re.I)),
]

def num(s: str) -> float:
    return float(s.replace(",", ""))

def main() -> int:
    m2_vals, pct_vals = [], []
    m2_by_type = collections.defaultdict(list)
    pct_by_type = collections.defaultdict(list)
    comp = collections.defaultdict(collections.Counter)
    count_phr = collections.Counter()
    rows = 0
    for frame in iter_annotations(["input", "output", "type", "category"], row_groups=range(14)):
        rows += len(frame)
        sub = frame[frame.category.isin(["area", "count"])]
        for i, o, t, c in zip(sub.input, sub.output, sub.type, sub.category, strict=False):
            key = f"{t}|{c}"
            if c == "area":
                mv = [num(x) for x in M2.findall(i)]
                pv = [num(x) for x in PCT.findall(i)]
                m2_vals.extend(mv); pct_vals.extend(pv)
                m2_by_type[key].extend(mv); pct_by_type[key].extend(pv)
            hit = False
            for name, rx in COMPARATOR:
                if rx.search(i):
                    comp[key][name] += 1; hit = True
            if not hit:
                comp[key]["none/equality"] += 1
            if c == "count" and t == "binary":
                m = re.search(r"(at least|fewer than|more than|exactly|at most)\s+(\w+)", i, re.I)
                if m: count_phr[f"{m.group(1).lower()} {m.group(2).lower()}"] += 1

    print(f"rows scanned (train+val): {rows:,}\n")
    print("### AREA UNITS — which form, and how often ###")
    for key in sorted(set(m2_by_type) | set(pct_by_type)):
        a, b = len(m2_by_type[key]), len(pct_by_type[key])
        print(f"  {key:16s} m2-values={a:>7,}   percent-values={b:>7,}")
    print()
    print("### m2 ROUNDING GRANULARITY (architecture expects nearest 1,000 m2) ###")
    s = pd.Series(m2_vals)
    print(f"  n={len(s):,}  min={s.min():,.0f}  median={s.median():,.0f}  max={s.max():,.0f}")
    for d in (10, 100, 1000, 10000):
        print(f"  divisible by {d:>6,}: {100*(s % d == 0).mean():6.2f}%")
    print(f"  distinct values: {s.nunique():,}")
    gaps = pd.Series(sorted(s.unique())).diff().dropna()
    print(f"  gaps between consecutive distinct values: min={gaps.min():,.0f} "
          f"median={gaps.median():,.0f} mode={gaps.mode().iloc[0]:,.0f}")
    print()
    print("### PERCENT GRANULARITY ###")
    p = pd.Series(pct_vals)
    print(f"  n={len(p):,}  min={p.min()}  median={p.median()}  max={p.max()}")
    for d in (0.1, 1, 5, 10):
        print(f"  divisible by {d:>5}: {100*((p / d).round() - (p / d)).abs().lt(1e-9).mean():6.2f}%")
    print(f"  distinct values: {p.nunique():,}  -> {sorted(p.unique())[:18]}")
    print()
    print("### COMPARATOR PHRASING per task ###")
    for key in sorted(comp):
        tot = sum(comp[key].values())
        top = ", ".join(f"{k} {100*v/tot:.1f}%" for k, v in comp[key].most_common(5))
        print(f"  {key:16s} {top}")
    print()
    print("### binary|count phrasings ###")
    for k, v in count_phr.most_common(12):
        print(f"  {v:>7,}  '{k}'")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "rows_scanned": rows,
        "m2": {"n": len(s), "min": float(s.min()), "median": float(s.median()),
               "max": float(s.max()), "nunique": int(s.nunique()),
               "pct_divisible": {str(d): round(100*float((s % d == 0).mean()), 3) for d in (10,100,1000,10000)},
               "gap_median": float(gaps.median()), "gap_min": float(gaps.min())},
        "percent": {"n": len(p), "min": float(p.min()), "max": float(p.max()),
                    "nunique": int(p.nunique()), "values": sorted(map(float, p.unique()))[:40]},
        "unit_counts_by_task": {k: {"m2": len(m2_by_type[k]), "pct": len(pct_by_type[k])}
                                 for k in sorted(set(m2_by_type)|set(pct_by_type))},
        "comparators": {k: dict(v) for k, v in comp.items()},
        "binary_count_phrasings": dict(count_phr.most_common(30)),
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
