"""S3 items 6,7,9,10 — distractor spacing, near-miss structure, answer priors, qualifiers."""
from __future__ import annotations

import collections
import json
import re

import pandas as pd

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f06_boundaries.json"
OPTLET = re.compile(r"(?:^|[,;]\s*|\s)([a-d])\)\s*(.+?)(?=(?:[,;]\s*|\s)[a-d]\)|$)")
RANGE = re.compile(r"([\d,\.]+)\s*to\s*([\d,\.]+)\s*(%|m2|m²)?", re.I)
INT = re.compile(r"^\s*([\d,]+)\s*$")
QUAL = re.compile(r"<ref>(.*?)</ref>")
PCT = re.compile(r"([\d]+(?:\.\d+)?)\s*%")
M2 = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:m2|m\^2|m²|square met(?:er|re)s?)", re.I)

BASE19 = None
def strip_qual(ref: str) -> tuple[str | None, str]:
    """Split '<qualifier> of <class>' into (qualifier, class)."""
    r = ref.strip().lower()
    m = re.match(r"^(.*?)\s+(?:of|in)\s+(.*)$", r)
    if m and BASE19 and m.group(2).replace(",", "") in BASE19:
        return m.group(1), m.group(2)
    return None, r

def main() -> int:
    global BASE19
    md = pd.read_parquet(project_root() / "data/raw/reben/metadata.parquet", columns=["labels"])
    BASE19 = {c.lower().replace(",", "") for lst in md.labels for c in lst}

    area_gaps, count_gaps = [], []
    area_opt_widths = []
    priors = collections.defaultdict(collections.Counter)
    quals = collections.Counter()
    adjacency_words = collections.Counter()
    eq_area_examples, eq_count_examples = [], []
    # near-miss: (patch, class, category) -> list of (stated_decile, answer)
    pairs = collections.defaultdict(list)
    rows = 0
    for frame in iter_annotations(["input","output","type","category","patch_id"], row_groups=range(14)):
        rows += len(frame)
        for i,o,t,c,pid in zip(frame.input, frame.output, frame.type, frame.category, frame.patch_id, strict=False):
            priors[f"{t}|{c}"][o if len(o) < 40 else "<LONG>"] += 1
            if t == "mcq" and c in ("area","count"):
                seg = i.split("?",1)[-1] if "?" in i else i
                vals = []
                for _l, txt in OPTLET.findall(seg):
                    txt = txt.strip().rstrip(".")
                    rm = RANGE.search(txt)
                    if rm:
                        lo, hi = float(rm.group(1).replace(",","")), float(rm.group(2).replace(",",""))
                        vals.append(lo); area_opt_widths.append(hi-lo); continue
                    im = INT.match(txt)
                    if im: vals.append(float(im.group(1).replace(",","")))
                vals = sorted(set(vals))
                if len(vals) >= 2:
                    d = [round(b-a,4) for a,b in zip(vals, vals[1:], strict=False)]
                    (area_gaps if c=="area" else count_gaps).extend(d)
            if t == "binary" and c in ("area","count"):
                if not re.search(r"at least|fewer than|more than|at most|less than|over |exceed|no more|no less", i, re.I):
                    (eq_area_examples if c=="area" else eq_count_examples).append(i)
                pm = PCT.search(i); mm = M2.search(i)
                stated = float(pm.group(1)) if pm else (float(mm.group(1).replace(",",""))/14400 if mm else None)
                if stated is not None:
                    cls = next((b for b in BASE19 if b in i.lower()), None)
                    if cls: pairs[(pid, cls, c)].append((stated, o, i))
            if "<ref>" in i:
                for r in QUAL.findall(i):
                    q, _base = strip_qual(r)
                    quals[q if q else "<none>"] += 1
            if c == "adjacency":
                for w in ("adjacent","next to","side by side","border","touch","contact","neighbour",
                          "neighbor","abut","meet"):
                    if w in i.lower(): adjacency_words[w] += 1
    print(f"rows scanned (train+val): {rows:,}\n")
    print("### item 6 — MCQ DISTRACTOR SPACING ###")
    ag, cg = pd.Series(area_gaps), pd.Series(count_gaps)
    print(f"  area  option-gap: n={len(ag):,} min={ag.min()} median={ag.median()} "
          f"mode={ag.mode().iloc[0]} max={ag.max()}  distinct={sorted(ag.unique())[:10]}")
    print(f"  area  option range WIDTH: median={pd.Series(area_opt_widths).median()} "
          f"distinct={sorted(set(area_opt_widths))[:8]}")
    print(f"  count option-gap: n={len(cg):,} min={cg.min()} median={cg.median()} "
          f"mode={cg.mode().iloc[0]} max={cg.max()}  distinct={sorted(cg.unique())[:10]}")
    print()
    print("### item 7 — BINARY NEAR-MISS STRUCTURE ###")
    deltas = {"area": [], "count": []}
    for (pid,cls,cat), lst in pairs.items():
        yes = [v for v,a,_ in lst if a=="yes"]
        if not yes: continue
        truth = yes[0]
        for v,a,_ in lst:
            if a=="no": deltas[cat].append(abs(v-truth))
    for cat, dv in deltas.items():
        if dv:
            s = pd.Series(dv)
            print(f"  {cat}: n={len(s):,} of NO answers paired with a YES on same (patch,class)")
            print(f"     |stated-true| deciles: min={s.min()} p25={s.quantile(.25)} "
                  f"median={s.median()} p75={s.quantile(.75)} max={s.max()}")
            print(f"     distribution: {dict(sorted(collections.Counter(s.round(1)).items())[:12])}")
    print()
    print("### equality-form binary examples (no comparator matched) ###")
    for e in eq_area_examples[:4]: print(f"   AREA : {e[:110]}")
    for e in eq_count_examples[:4]: print(f"   COUNT: {e[:110]}")
    print()
    print("### item 8 — ADJACENCY PHRASING ###")
    for w,n in adjacency_words.most_common(): print(f"   {n:>7,}  '{w}'")
    print()
    print("### item 10 — REFERRING QUALIFIERS ###")
    for q,n in quals.most_common(14): print(f"   {n:>7,}  {q}")
    print()
    print("### item 9 — ANSWER PRIORS ###")
    for k in sorted(priors):
        tot = sum(priors[k].values())
        top = ", ".join(f"{a}={100*v/tot:.1f}%" for a,v in priors[k].most_common(4))
        print(f"   {k:22s} n={tot:>8,}  {top}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "rows": rows,
        "mcq_area_option_gaps": dict(collections.Counter(area_gaps).most_common(20)),
        "mcq_area_range_widths": dict(collections.Counter(area_opt_widths).most_common(10)),
        "mcq_count_option_gaps": dict(collections.Counter(count_gaps).most_common(20)),
        "binary_near_miss_deltas": {k: dict(sorted(collections.Counter(pd.Series(v).round(1)).items()))
                                    for k,v in deltas.items() if v},
        "adjacency_words": dict(adjacency_words),
        "referring_qualifiers": dict(quals.most_common(40)),
        "answer_priors": {k: dict(v.most_common(30)) for k,v in priors.items()},
        "equality_examples": {"area": eq_area_examples[:10], "count": eq_count_examples[:10]},
    }, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
