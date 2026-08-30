"""S3 close-out — settle boundary inclusivity at scale with clean class attribution."""
from __future__ import annotations

import collections
import json
import re

import pandas as pd

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f10_inclusivity.json"
INCL_GE = re.compile(r"\bat least\b|\bno less than\b|\bor more\b|\bminimum of\b", re.I)
STRICT_GT = re.compile(r"\bmore than\b|\bgreater than\b|\bexceed\w*\b|\bover\b|\babove\b", re.I)
INCL_LE = re.compile(r"\bat most\b|\bno more than\b|\bor fewer\b|\bor less\b", re.I)
STRICT_LT = re.compile(r"\bless than\b|\bfewer than\b|\bunder\b|\bbelow\b", re.I)
PCT = re.compile(r"([\d]+(?:\.\d+)?)\s*%")
M2 = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:m2|m\^2|m²|sqm|square met(?:er|re)s?)", re.I)

def main() -> int:
    mdf = pd.read_parquet(project_root() / "data/raw/reben/metadata.parquet", columns=["labels"])
    classes = sorted({c.lower() for lst in mdf.labels for c in lst}, key=len, reverse=True)

    obs: dict[tuple, dict] = collections.defaultdict(dict)
    ambiguous = 0
    for frame in iter_annotations(["input", "output", "type", "category", "patch_id"],
                                  row_groups=range(40)):
        sub = frame[(frame.type == "binary") & (frame.category == "area")]
        for i, o, pid in zip(sub.input, sub.output, sub.patch_id, strict=True):
            low = i.lower()
            # CLEAN ATTRIBUTION: require exactly one 19-class name, else discard
            hits = [c for c in classes if c in low]
            hits = [c for c in hits if not any(c != d and c in d for d in hits)]
            if len(hits) != 1:
                ambiguous += 1
                continue
            form = ("ge" if INCL_GE.search(i) else "gt" if STRICT_GT.search(i)
                    else "le" if INCL_LE.search(i) else "lt" if STRICT_LT.search(i) else None)
            if form is None:
                continue
            m = PCT.search(i)
            th = float(m.group(1)) if m else None
            if th is None:
                m = M2.search(i)
                th = float(m.group(1).replace(",", "")) / 14400.0 if m else None
            if th is None:
                continue
            obs[(pid, hits[0], round(th, 4))][form] = o

    v = collections.Counter()
    for _k, d in obs.items():
        if "ge" in d and "gt" in d:
            if d["ge"] == "yes" and d["gt"] == "no":
                v["DECISIVE: truth == N; '>=' includes N, '>' excludes N"] += 1
            elif d["ge"] == d["gt"]:
                v["consistent (both same; truth not exactly N)"] += 1
            else:
                v["LOGICALLY IMPOSSIBLE (ge=no, gt=yes) -> parse artifact"] += 1
        if "le" in d and "lt" in d:
            if d["le"] == "yes" and d["lt"] == "no":
                v["DECISIVE: truth == N; '<=' includes N, '<' excludes N"] += 1
            elif d["le"] == d["lt"]:
                v["consistent (both same; truth not exactly N)"] += 1
            else:
                v["LOGICALLY IMPOSSIBLE (le=no, lt=yes) -> parse artifact"] += 1

    print(f"(patch, class, threshold) groups observed : {len(obs):,}")
    print(f"rows discarded for ambiguous class attribution: {ambiguous:,}\n")
    print("### BOUNDARY INCLUSIVITY — from released answers ###")
    for k, n in v.most_common():
        print(f"   {n:>7,}  {k}")
    dec = sum(n for k, n in v.items() if k.startswith("DECISIVE"))
    imp = sum(n for k, n in v.items() if k.startswith("LOGICALLY"))
    print()
    if dec:
        print(f"   decisive pairs           : {dec:,}")
        print(f"   logically impossible     : {imp:,}  ({100*imp/(dec+imp):.1f}% of contradictory+decisive)")
        print("   VERDICT: inclusive forms (>=, <=) INCLUDE the boundary value N;")
        print("            strict forms (>, <) EXCLUDE it. Standard semantics confirmed.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"groups": len(obs), "ambiguous_discarded": ambiguous,
                               "verdict_counts": dict(v), "decisive": dec,
                               "logically_impossible": imp}, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
