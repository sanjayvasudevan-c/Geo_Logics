"""S3 item 3 — is metadata an INPUT or a LABEL? Decides the M5 gate."""
from __future__ import annotations

import collections
import json
import re

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f07_metadata.json"
OPTLET = re.compile(r"(?:^|[,;]\s*|\s)([a-d])\)\s*(.+?)(?=(?:[,;]\s*|\s)[a-d]\)|$)")

def main() -> int:
    agree = collections.Counter(); leak = collections.Counter(); rows = 0
    for frame in iter_annotations(
        ["input","output","type","category","country","season","climate_zone","latitude","longitude"],
        row_groups=range(8)):
        rows += len(frame)
        for r in frame.itertuples():
            # does the metadata COLUMN equal the correct MCQ option?
            if r.type == "mcq" and r.category in ("country","season","climate zone"):
                col = {"country": r.country, "season": r.season, "climate zone": r.climate_zone}[r.category]
                seg = r.input.split("?",1)[-1] if "?" in r.input else r.input
                opts = {l: t.strip().rstrip(".") for l, t in OPTLET.findall(seg)}
                chosen = opts.get(str(r.output).strip())
                if chosen is not None:
                    agree[r.category] += int(chosen.strip().lower() == str(col).strip().lower())
                    leak[r.category] += 1
            # does the QUESTION TEXT ever contain the metadata value (i.e. given away as input)?
            low = r.input.lower()
            for nm, val in (("country", r.country), ("season", r.season)):
                if str(val).lower() in low and r.category != nm:
                    leak[f"{nm}_in_question_text"] += 1
    print(f"rows scanned (train+val): {rows:,}\n")
    print("### Does the metadata COLUMN equal the correct MCQ answer? ###")
    for c in ("country","season","climate zone"):
        n = leak[c]
        if n: print(f"  {c:14s} {agree[c]:,}/{n:,} = {100*agree[c]/n:.2f}% agreement")
    print()
    print("### Does the metadata value leak into question text of OTHER tasks? ###")
    for k in ("country_in_question_text","season_in_question_text"):
        print(f"  {k:30s} {leak[k]:,}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": rows, "agreement": dict(agree), "totals": dict(leak)},
                              indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
