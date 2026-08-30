"""S3 follow-up — what remains fittable in S7 once area is decile-quantised?"""
from __future__ import annotations

import collections
import json
import re

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f08_s7_residual.json"
OPTLET = re.compile(r"(?:^|[,;]\s*|\s)([a-d])\)\s*(.+?)(?=(?:[,;]\s*|\s)[a-d]\)|$)")
RANGE = re.compile(r"([\d,\.]+)\s*to\s*([\d,\.]+)")
BETWEEN = re.compile(r"between\s+([\d,\.]+)\s*(%|square meters|sqm|m2|m²)?\s*and\s+([\d,\.]+)", re.I)

def main() -> int:
    area_opt_forms = collections.Counter()
    endpoints_shared = collections.Counter()
    binary_area_forms = collections.Counter()
    binary_count_forms = collections.Counter()
    rows = 0
    for frame in iter_annotations(["input","type","category"], row_groups=range(10)):
        rows += len(frame)
        sub = frame[frame.category.isin(["area","count"])]
        for i,t,c in zip(sub.input, sub.type, sub.category, strict=False):
            if t == "mcq" and c == "area":
                seg = i.split("?",1)[-1] if "?" in i else i
                vals = []
                for _l, txt in OPTLET.findall(seg):
                    rm = RANGE.search(txt)
                    area_opt_forms["range" if rm else "point"] += 1
                    if rm: vals.append((float(rm.group(1).replace(",","")), float(rm.group(2).replace(",",""))))
                vals.sort()
                for (a_lo,a_hi),(b_lo,b_hi) in zip(vals, vals[1:], strict=False):
                    endpoints_shared["touching" if abs(a_hi-b_lo) < 1e-9 else "gapped"] += 1
            if t == "binary" and c == "area":
                if BETWEEN.search(i): binary_area_forms["between_range"] += 1
                elif re.search(r"at least|no less than|minimum", i, re.I): binary_area_forms["at_least"] += 1
                elif re.search(r"more than|greater than|exceed|over ", i, re.I): binary_area_forms["more_than"] += 1
                elif re.search(r"at most|no more than|less than|fewer|under", i, re.I): binary_area_forms["at_most"] += 1
                else: binary_area_forms["other"] += 1
            if t == "binary" and c == "count":
                if re.search(r"exactly", i, re.I): binary_count_forms["exactly_n"] += 1
                elif re.search(r"at least|or more", i, re.I): binary_count_forms["at_least_n"] += 1
                elif re.search(r"fewer than|less than|at most|no more", i, re.I): binary_count_forms["at_most_n"] += 1
                elif re.search(r"more than", i, re.I): binary_count_forms["more_than_n"] += 1
                elif re.search(r"multiple|one or more|any", i, re.I): binary_count_forms["presence_like"] += 1
                else: binary_count_forms["other"] += 1
    print(f"rows scanned (train+val): {rows:,}\n")
    tot = sum(area_opt_forms.values())
    print("### Are MCQ area options ranges or point values? ###")
    for k,v in area_opt_forms.most_common(): print(f"   {k:8s} {v:>8,}  {100*v/tot:5.1f}%")
    print()
    te = sum(endpoints_shared.values())
    print("### Do adjacent MCQ area ranges SHARE an endpoint? (boundary convention matters if so) ###")
    for k,v in endpoints_shared.most_common(): print(f"   {k:9s} {v:>8,}  {100*v/te:5.1f}%")
    print()
    tb = sum(binary_area_forms.values())
    print("### binary|area question FORM ###")
    for k,v in binary_area_forms.most_common(): print(f"   {k:14s} {v:>8,}  {100*v/tb:5.1f}%")
    print()
    tc = sum(binary_count_forms.values())
    print("### binary|count question FORM ###")
    for k,v in binary_count_forms.most_common(): print(f"   {k:14s} {v:>8,}  {100*v/tc:5.1f}%")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "rows": rows, "mcq_area_option_forms": dict(area_opt_forms),
        "mcq_area_adjacent_endpoints": dict(endpoints_shared),
        "binary_area_forms": dict(binary_area_forms),
        "binary_count_forms": dict(binary_count_forms)}, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
