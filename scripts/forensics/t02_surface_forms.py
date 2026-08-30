"""S4 item 3 — extract the REAL natural-language surface forms for each class.

Derived from actual question text (train+val), not invented. Records anything unresolvable.
"""
from __future__ import annotations

import collections
import json
import re

import pandas as pd

from satquery.evaluation.forensics import iter_annotations
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/t02_surface_forms.json"
REF = re.compile(r"<ref>(.*?)</ref>")
OPTLET = re.compile(r"(?:^|[,;]\s*|\s)([a-d])\)\s*(.+?)(?=(?:[,;]\s*|\s)[a-d]\)|$)")
QUALIFIER = re.compile(
    r"^(largest|smallest)\s+(?:patch|continuous area|contiguous area|connected region|"
    r"continuous region|connected patch|contiguous region|continuous patch)\s+(?:of|in)\s+", re.I)

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip().rstrip(".").replace(",", ""))

def main() -> int:
    md = pd.read_parquet(project_root() / "data/raw/reben/metadata.parquet", columns=["labels"])
    canon = sorted({c for lst in md.labels for c in lst})
    canon_n = {norm(c): c for c in canon}
    # singular<->plural bridge
    def variants(n: str) -> set[str]:
        out = {n}
        for a, b in (("s", ""), ("", "s")):
            if a and n.endswith(a):
                out.add(n[:-1])
            elif b:
                out.add(n + b)
        return out

    surfaces = collections.Counter()
    unresolved = collections.Counter()
    for frame in iter_annotations(["input", "type", "category"], row_groups=range(12)):
        for i, t, c in zip(frame.input, frame.type, frame.category, strict=True):
            found = []
            for r in REF.findall(i):
                found.append(QUALIFIER.sub("", r.strip()))
            if t == "mcq" and c in ("presence", "adjacency"):
                seg = i.split("?", 1)[-1] if "?" in i else i
                for _l, txt in OPTLET.findall(seg):
                    found.extend(p.strip() for p in re.split(r"\band\b", txt) if p.strip())
            for f in found:
                surfaces[norm(f)] += 1

    resolved, unmatched = {}, {}
    for s, n in surfaces.items():
        hit = None
        for cn, orig in canon_n.items():
            if s in variants(cn) or cn in variants(s):
                hit = orig
                break
        if hit is None:
            # try containment (e.g. "transitional woodlands or shrubs" vs "transitional woodland shrub")
            toks = set(s.split())
            best, score = None, 0.0
            for cn, orig in canon_n.items():
                ct = set(cn.split())
                j = len(toks & ct) / max(1, len(toks | ct))
                if j > score:
                    best, score = orig, j
            if score >= 0.55:
                hit = best
            else:
                unmatched[s] = n
                unresolved[s] += n
        if hit:
            resolved.setdefault(hit, collections.Counter())[s] = n

    print(f"distinct surface forms observed : {len(surfaces):,}")
    print(f"resolved to a canonical class   : {sum(len(v) for v in resolved.values()):,}")
    print(f"UNRESOLVED                      : {len(unmatched):,}\n")
    print("### surface forms per canonical class ###")
    for cls in sorted(resolved):
        forms = resolved[cls]
        shown = ", ".join(f"{f}({n:,})" for f, n in forms.most_common(6))
        print(f"  {cls}\n      {shown}")
    if unmatched:
        print("\n### UNRESOLVED surface forms (reported, not dropped) ###")
        for s, n in sorted(unmatched.items(), key=lambda kv: -kv[1])[:25]:
            print(f"   {n:>7,}  {s}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "canonical_19": canon,
        "surface_forms_by_class": {k: dict(v) for k, v in resolved.items()},
        "unresolved": dict(unmatched),
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
