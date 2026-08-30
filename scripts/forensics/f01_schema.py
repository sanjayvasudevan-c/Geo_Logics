"""S3 item 1 — full schema, dtypes, null rates, cardinality, examples. Train/val only."""
from __future__ import annotations

import contextlib
import json

import pandas as pd

from satquery.evaluation.forensics import FORENSIC_SPLITS, iter_annotations, open_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f01_schema.json"

def main() -> int:
    pf = open_annotations()
    print(f"file rows (ALL splits) : {pf.metadata.num_rows:,}")
    print(f"row groups             : {pf.metadata.num_row_groups}")
    print("arrow schema           :")
    for f in pf.schema_arrow:
        print(f"    {f.name:16s} {f.type}")
    print()
    n = 0
    nulls: dict[str, int] = {}
    uniq: dict[str, set] = {}
    ex: dict[str, list] = {}
    lens: dict[str, list[int]] = {"input": [], "output": []}
    for frame in iter_annotations(splits=FORENSIC_SPLITS):
        n += len(frame)
        for c in frame.columns:
            nulls[c] = nulls.get(c, 0) + int(frame[c].isna().sum())
            if c not in uniq:
                uniq[c], ex[c] = set(), []
            if len(uniq[c]) < 200_000:
                with contextlib.suppress(TypeError):  # list-valued columns are unhashable
                    uniq[c].update(frame[c].dropna().unique().tolist())
            if len(ex[c]) < 3:
                ex[c].extend(map(str, frame[c].dropna().head(3).tolist()))
        for c in ("input", "output"):
            if c in frame.columns and len(lens[c]) < 400_000:
                lens[c].extend(frame[c].astype(str).str.len().tolist())
    print(f"train+validation rows  : {n:,}   (bench EXCLUDED by loader)")
    print()
    print(f"{'column':16s} {'nulls':>10s} {'null%':>7s} {'cardinality':>13s}  example")
    rec = {"rows_train_val": n, "columns": {}}
    for c in nulls:
        card = len(uniq[c]); capped = card >= 200_000
        print(f"{c:16s} {nulls[c]:>10,} {100*nulls[c]/n:>6.3f}% {card:>12,}{'+' if capped else ' '}  {ex[c][0][:48] if ex[c] else ''}")
        rec["columns"][c] = {"nulls": nulls[c], "null_pct": round(100*nulls[c]/n, 4),
                            "cardinality": card, "cardinality_capped": capped,
                            "examples": ex[c][:3]}
    print()
    for c, v in lens.items():
        s = pd.Series(v)
        print(f"{c} length: min {s.min()} p50 {int(s.quantile(.5))} p95 {int(s.quantile(.95))} max {s.max()}")
        rec["columns"][c]["char_len"] = {"min": int(s.min()), "p50": int(s.quantile(.5)),
                                         "p95": int(s.quantile(.95)), "max": int(s.max())}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
