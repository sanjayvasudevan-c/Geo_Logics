"""S3 item 2 — which class vocabulary do the questions actually use? Purely empirical."""
from __future__ import annotations

import collections
import json
import re

import pandas as pd

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f03_classes.json"
REF = re.compile(r"<ref>(.*?)</ref>")
OPT = re.compile(r"[a-d]\)\s*([^,]+?)(?=,\s*[a-d]\)|$)")

def main() -> int:
    # 1. reBEN's official 19-class IMAGE-LEVEL vocabulary, straight from metadata.parquet
    md = pd.read_parquet(project_root() / "data/raw/reben/metadata.parquet", columns=["labels"])
    ben19 = collections.Counter()
    for lst in md.labels:
        ben19.update(lst)
    print(f"=== reBEN metadata.parquet 'labels' vocabulary: {len(ben19)} distinct ===")
    for c, n in ben19.most_common():
        print(f"   {n:>8,}  {c}")
    print()

    # 2. Class names appearing in questions, via <ref> tags and mcq/presence options
    refs, opts = collections.Counter(), collections.Counter()
    for frame in iter_annotations(["input", "type", "category"], row_groups=range(10)):
        for i, t, c in zip(frame.input, frame.type, frame.category, strict=False):
            if "<ref>" in i:
                refs.update(m.strip().lower() for m in REF.findall(i))
            if t == "mcq" and c == "presence":
                seg = i.split("?", 1)[-1] if "?" in i else i
                opts.update(m.strip().rstrip(".").lower() for m in OPT.findall(seg))
    print(f"=== <ref> tag vocabulary: {len(refs)} distinct ===")
    for c, n in refs.most_common(30):
        print(f"   {n:>7,}  {c}")
    print()
    print(f"=== mcq/presence option vocabulary: {len(opts)} distinct (top 30) ===")
    for c, n in opts.most_common(30):
        print(f"   {n:>7,}  {c}")
    print()

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.lower().strip().rstrip("."))
    ben_n = {norm(c) for c in ben19}
    ref_n = {norm(c) for c in refs}
    opt_n = {norm(c) for c in opts}
    print("=== OVERLAP ANALYSIS (normalised, singular/plural not yet reconciled) ===")
    print(f"  reBEN 19-class set          : {len(ben_n)}")
    print(f"  <ref> set                   : {len(ref_n)}")
    print(f"  mcq/presence option set     : {len(opt_n)}")
    print(f"  <ref> INTERSECT 19-class    : {len(ref_n & ben_n)}")
    print(f"  options INTERSECT 19-class  : {len(opt_n & ben_n)}")
    print(f"  options NOT in 19-class     : {sorted(opt_n - ben_n)[:15]}")
    print(f"  19-class NOT in options     : {sorted(ben_n - opt_n)[:15]}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "reben_19_labels": dict(ben19),
        "ref_tag_vocab": dict(refs),
        "mcq_presence_option_vocab": dict(opts.most_common(80)),
        "counts": {"reben19": len(ben_n), "ref": len(ref_n), "opts": len(opt_n),
                   "ref_int_19": len(ref_n & ben_n), "opt_int_19": len(opt_n & ben_n)},
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
