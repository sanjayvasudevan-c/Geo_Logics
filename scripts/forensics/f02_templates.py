"""S3 items 4/8/10 — mine question templates and answer vocabularies per (type, category)."""
from __future__ import annotations

import collections
import json
import re

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f02_templates.json"
GROUPS = 12  # sample of row groups; each ~122k rows

NUM = re.compile(r"\d[\d,\.]*")
def skeleton(text: str) -> str:
    """Replace numbers with <N>; keep structure for template counting."""
    return NUM.sub("<N>", text)

def main() -> int:
    tmpl: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
    ans: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
    n = 0
    for frame in iter_annotations(["input", "output", "type", "category"],
                                  row_groups=range(GROUPS)):
        n += len(frame)
        for t, c, i, o in zip(frame.type, frame.category, frame.input, frame.output, strict=False):
            tmpl[(t, c)][skeleton(i)] += 1
            ans[(t, c)][o if len(o) < 40 else "<LONG>"] += 1
    print(f"rows sampled (train+val, {GROUPS} row groups): {n:,}\n")
    rec = {}
    for key in sorted(tmpl, key=lambda k: -sum(tmpl[k].values())):
        t, c = key
        tot = sum(tmpl[key].values())
        print(f"=== {t} / {c} — {tot:,} rows, {len(tmpl[key]):,} distinct skeletons ===")
        for s, k in tmpl[key].most_common(4):
            print(f"   {100*k/tot:5.1f}%  {s[:118]}")
        av = ans[key]
        print(f"   answers: {len(av):,} distinct -> {[a for a,_ in av.most_common(6)]}")
        print()
        rec[f"{t}|{c}"] = {
            "rows": tot,
            "distinct_skeletons": len(tmpl[key]),
            "top_skeletons": [{"pct": round(100*k/tot,2), "text": s} for s,k in tmpl[key].most_common(8)],
            "distinct_answers": len(av),
            "top_answers": [{"answer": a, "n": k, "pct": round(100*k/tot,3)} for a,k in av.most_common(25)],
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
