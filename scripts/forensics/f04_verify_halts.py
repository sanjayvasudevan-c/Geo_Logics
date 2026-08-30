"""S3 — settle the two HALT conditions: class vocabulary level, and area units/rounding."""
from __future__ import annotations

import collections
import json
import re

import pandas as pd

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f04_halts.json"
# split options on the LETTER markers, so class names containing commas survive
OPT = re.compile(r"(?:^|[,;]\s*|\s)([a-d])\)\s*(.+?)(?=(?:[,;]\s*|\s)[a-d]\)|$)")

CLC_L1 = ["artificial surfaces", "agricultural areas", "forest and semi natural areas",
          "forest and semi-natural areas", "wetlands", "water bodies"]
CLC_L2_ONLY = ["mine, dump and construction sites", "artificial, non-agricultural vegetated areas",
               "heterogeneous agricultural areas", "forests",
               "scrub and/or herbaceous vegetation associations",
               "open spaces with little or no vegetation", "road and rail networks"]
# CLC L3 names that are NOT in the reBEN 19-class scheme
CLC_L3_NOT19 = ["continuous urban fabric", "discontinuous urban fabric", "green urban areas",
                "sport and leisure facilities", "non-irrigated arable land",
                "permanently irrigated land", "rice fields", "vineyards",
                "fruit trees and berry plantations", "olive groves", "annual crops",
                "natural grasslands", "sclerophyllous vegetation", "sparsely vegetated areas",
                "bare rocks", "burnt areas", "glaciers and perpetual snow", "salines",
                "peat bogs", "salt marshes", "water courses", "water bodies", "coastal lagoons",
                "estuaries", "sea and ocean", "port areas", "airports", "mineral extraction sites",
                "dump sites", "construction sites", "beaches", "dunes", "sands"]

AREA_UNIT = {
    "percent_sign": re.compile(r"\d\s*%"),
    "square_metres": re.compile(r"\b(m2|m\^2|m²|square (?:met|meter|metre))", re.I),
    "hectare": re.compile(r"\bhectare|\bha\b", re.I),
    "km2": re.compile(r"\bkm2|km²", re.I),
    "thousand_m2": re.compile(r"\d{1,3},?000\s*(m2|m²|square)", re.I),
}

def main() -> int:
    md = pd.read_parquet(project_root() / "data/raw/reben/metadata.parquet", columns=["labels"])
    ben19 = sorted({c for lst in md.labels for c in lst})
    n19 = {c.lower().replace(",", "") for c in ben19}

    opts = collections.Counter()
    unit_hits = collections.Counter()
    unit_by_cat = collections.defaultdict(collections.Counter)
    l1_hits, l2_hits, l3not19_hits = collections.Counter(), collections.Counter(), collections.Counter()
    cap_units = collections.Counter()
    rows = 0
    for frame in iter_annotations(["input", "output", "type", "category"], row_groups=range(14)):
        rows += len(frame)
        for i, o, t, c in zip(frame.input, frame.output, frame.type, frame.category, strict=False):
            low = i.lower()
            for name, rx in AREA_UNIT.items():
                if rx.search(i):
                    unit_hits[name] += 1
                    if c in ("area",):
                        unit_by_cat[f"{t}|{c}"][name] += 1
            for nm in CLC_L1:
                if nm in low: l1_hits[nm] += 1
            for nm in CLC_L2_ONLY:
                if nm in low: l2_hits[nm] += 1
            for nm in CLC_L3_NOT19:
                if re.search(rf"\b{re.escape(nm)}\b", low): l3not19_hits[nm] += 1
            if t == "mcq" and c == "presence":
                seg = i.split("?", 1)[-1] if "?" in i else i
                for _letter, text in OPT.findall(seg):
                    opts[text.strip().rstrip(".").lower().replace(",", "")] += 1
            if t == "captioning":
                for name, rx in AREA_UNIT.items():
                    if rx.search(o): cap_units[name] += 1

    print(f"rows scanned (train+val): {rows:,}\n")
    print("### HALT CHECK 1 — which class vocabulary do questions use? ###")
    print(f"reBEN 19-class vocabulary size          : {len(ben19)}")
    print(f"mcq/presence distinct options extracted : {len(opts)}")
    outside = {k: v for k, v in opts.items() if k not in n19}
    print(f"options INSIDE the 19-class set         : {len(opts)-len(outside)}")
    print(f"options OUTSIDE the 19-class set        : {len(outside)}  {sorted(outside)[:8]}")
    print()
    print(f"CLC Level-1 group names found in questions : {sum(l1_hits.values()):,}  {dict(l1_hits)}")
    print(f"CLC Level-2-only names found               : {sum(l2_hits.values()):,}  {dict(l2_hits)}")
    print(f"CLC L3 names NOT in the 19-class scheme     : {sum(l3not19_hits.values()):,}")
    if l3not19_hits: print(f"    {dict(l3not19_hits.most_common(10))}")
    print()
    print("### HALT CHECK 2 — area units and rounding ###")
    print(f"unit markers across ALL questions: {dict(unit_hits)}")
    for k, v in unit_by_cat.items():
        print(f"  area questions {k}: {dict(v)}")
    print(f"unit markers in CAPTION answers  : {dict(cap_units)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "rows_scanned": rows, "reben19": ben19,
        "mcq_presence_options": dict(opts), "options_outside_19": sorted(outside),
        "clc_l1_hits": dict(l1_hits), "clc_l2_only_hits": dict(l2_hits),
        "clc_l3_not_in_19_hits": dict(l3not19_hits),
        "unit_hits_all_questions": dict(unit_hits),
        "unit_hits_area_questions": {k: dict(v) for k, v in unit_by_cat.items()},
        "unit_hits_caption_answers": dict(cap_units),
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
