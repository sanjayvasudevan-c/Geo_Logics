"""S3 close-out — (A) resolve boundary inclusivity from released answers directly;
(B) re-pass the unmatched binary forms to see if they are genuinely non-comparator."""
from __future__ import annotations

import collections
import json
import re

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f09_boundary_residual.json"

# Ordered: most specific first, so "at least" is not swallowed by a looser pattern.
COMPARATORS = [
    ("at_least",   re.compile(r"\bat least\b|\bno less than\b|\bor more\b|\bminimum of\b|\bor greater\b", re.I)),
    ("at_most",    re.compile(r"\bat most\b|\bno more than\b|\bor fewer\b|\bor less\b|\bmaximum of\b", re.I)),
    ("more_than",  re.compile(r"\bmore than\b|\bgreater than\b|\bexceed\w*\b|\bover\b|\babove\b|\bsurpass\w*\b", re.I)),
    ("less_than",  re.compile(r"\bless than\b|\bfewer than\b|\bunder\b|\bbelow\b", re.I)),
    ("between",    re.compile(r"\bbetween\b|\bfrom\b.*\bto\b|\brange\b", re.I)),
    ("exactly",    re.compile(r"\bexactly\b|\bprecisely\b", re.I)),
]
PCT = re.compile(r"([\d]+(?:\.\d+)?)\s*%")
M2 = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:m2|m\^2|m²|sqm|square met(?:er|re)s?)", re.I)
NUMWORD = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,
           "eight":8,"nine":9,"ten":10,"a single":1,"any":None}
NUM = re.compile(r"\d[\d,\.]*")

def classify(text: str) -> str | None:
    for name, rx in COMPARATORS:
        if rx.search(text):
            return name
    return None

def threshold_pct(text: str) -> float | None:
    m = PCT.search(text)
    if m:
        return float(m.group(1))
    m = M2.search(text)
    if m:
        return float(m.group(1).replace(",", "")) / 14400.0
    return None

def main() -> int:
    # (A) inclusivity: collect (comparator, threshold, answer) per (patch, class)
    obs: dict[tuple[str, str], list[tuple[str, float, str]]] = collections.defaultdict(list)
    # (B) residual: skeletons of anything still unclassified
    residual = {"area": collections.Counter(), "count": collections.Counter()}
    residual_n = collections.Counter()
    total_n = collections.Counter()
    classified_n = collections.Counter()

    md_classes = None
    import pandas as pd
    mdf = pd.read_parquet(project_root() / "data/raw/reben/metadata.parquet", columns=["labels"])
    md_classes = sorted({c.lower() for lst in mdf.labels for c in lst}, key=len, reverse=True)

    for frame in iter_annotations(["input", "output", "type", "category", "patch_id"],
                                  row_groups=range(16)):
        sub = frame[(frame.type == "binary") & (frame.category.isin(["area", "count"]))]
        for i, o, c, pid in zip(sub.input, sub.output, sub.category, sub.patch_id, strict=True):
            total_n[c] += 1
            comp = classify(i)
            if comp is None:
                residual_n[c] += 1
                residual[c][NUM.sub("<N>", i)] += 1
                continue
            classified_n[c] += 1
            if c == "area" and comp in ("at_least", "at_most", "more_than", "less_than"):
                th = threshold_pct(i)
                if th is None:
                    continue
                cls = next((b for b in md_classes if b in i.lower()), None)
                if cls:
                    obs[(pid, cls)].append((comp, th, o))

    print("### (B) RESIDUAL RE-PASS — are unmatched forms genuinely non-comparator? ###")
    for c in ("area", "count"):
        tot, res = total_n[c], residual_n[c]
        print(f"  binary/{c}: {tot:,} scanned, {classified_n[c]:,} classified, "
              f"{res:,} residual = {100*res/tot:.2f}%  (was 27.7% / 11.6% with the old regex)")
    print()
    for c in ("area", "count"):
        if residual[c]:
            print(f"  top residual skeletons — binary/{c}:")
            for s, k in residual[c].most_common(6):
                print(f"     {k:>6,}  {s[:104]}")
            print()

    print("### (A) BOUNDARY INCLUSIVITY — decided from released answers, no sweep ###")
    # Decisive pattern: same (patch,class), same threshold N, where an inclusive-form and a
    # strict-form comparator disagree => truth == N exactly, revealing each form's convention.
    verdict = collections.Counter()
    examples: list[str] = []
    for (_pid, _cls), rows in obs.items():
        by_th: dict[float, dict[str, str]] = collections.defaultdict(dict)
        for comp, th, ans in rows:
            by_th[th][comp] = ans
        for th, d in by_th.items():
            if "at_least" in d and "more_than" in d and d["at_least"] != d["more_than"]:
                # at_least=yes, more_than=no  => truth == th, and >= includes th
                if d["at_least"] == "yes" and d["more_than"] == "no":
                    verdict["at_least INCLUSIVE at N (>=), more_than STRICT (>)"] += 1
                    if len(examples) < 3:
                        examples.append(f"th={th}: at_least={d['at_least']}, more_than={d['more_than']}")
                else:
                    verdict["UNEXPECTED at_least/more_than polarity"] += 1
            if "at_most" in d and "less_than" in d and d["at_most"] != d["less_than"]:
                if d["at_most"] == "yes" and d["less_than"] == "no":
                    verdict["at_most INCLUSIVE at N (<=), less_than STRICT (<)"] += 1
                else:
                    verdict["UNEXPECTED at_most/less_than polarity"] += 1
    if verdict:
        for k, v in verdict.most_common():
            print(f"   {v:>6,}  {k}")
        for e in examples:
            print(f"   example: {e}")
    else:
        print("   INCONCLUSIVE — no (patch,class) had both an inclusive and a strict form")
        print("   at the SAME threshold, so the boundary cannot be pinned from pairs alone.")
    print(f"\n   (patch,class) groups with >=1 comparator observation: {len(obs):,}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "residual": {c: {"scanned": total_n[c], "classified": classified_n[c],
                         "residual": residual_n[c],
                         "residual_pct": round(100*residual_n[c]/total_n[c], 3),
                         "top_skeletons": dict(residual[c].most_common(25))}
                     for c in ("area", "count")},
        "inclusivity_verdict": dict(verdict),
        "groups_observed": len(obs),
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
