"""S8 Experiment O2 — caption oracle. Decides the M8 gate.

Ground-truth map -> M2 attributes -> template caption -> BLEU-4 against the released reference.

GATE (IMPLEMENTATION_MAP §3.8):
    BLEU-4 >= 35  -> raw templates suffice, SKIP M8
    10 <= BLEU < 35 -> BUILD M8 (a template->style rewriter)
    BLEU < 10     -> drop symbolic captioning, route to M7

Reference captions were paraphrased by a quantised Llama-4-Scout with explicit instructions to
diversify lexical and syntactic structure, which is directly adversarial to n-gram overlap. A
low BLEU here is therefore expected and is a statement about SURFACE FORM, not about whether the
facts are right.

BLEU-4 is implemented here (standard corpus BLEU with brevity penalty) rather than pulled in as
a dependency. METEOR and CIDEr are NOT computed — they need extra packages, and BLEU-4 is the
number the gate is defined on. That is stated rather than silently omitted.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
import sys

import numpy as np
import rasterio

from satquery.config import load_config
from satquery.evaluation.forensics import iter_annotations
from satquery.geometry import GeometryParams, extract_regions
from satquery.taxonomy import load_synonyms, load_taxonomy
from satquery.utils.paths import project_root

TILE = re.compile(r"_(T\d{2}[A-Z]{3})_\d+_\d+$")
TOKEN = re.compile(r"[a-z0-9]+")

def tok(s: str) -> list[str]:
    return TOKEN.findall(s.lower())

def ngrams(t: list[str], n: int) -> collections.Counter:
    return collections.Counter(tuple(t[i:i+n]) for i in range(len(t)-n+1))

def corpus_bleu(hyps: list[str], refs: list[str], max_n: int = 4) -> dict:
    """Standard corpus BLEU with brevity penalty."""
    num = [0]*max_n; den = [0]*max_n; hyp_len = ref_len = 0
    for h, r in zip(hyps, refs, strict=True):
        ht, rt = tok(h), tok(r)
        hyp_len += len(ht); ref_len += len(rt)
        for n in range(1, max_n+1):
            hn, rn = ngrams(ht, n), ngrams(rt, n)
            num[n-1] += sum(min(c, rn[g]) for g, c in hn.items())
            den[n-1] += max(sum(hn.values()), 0)
    precs = [(num[i]/den[i]) if den[i] else 0.0 for i in range(max_n)]
    if min(precs) <= 0:
        geo = 0.0
    else:
        geo = math.exp(sum(math.log(p) for p in precs)/max_n)
    bp = 1.0 if hyp_len > ref_len else (math.exp(1 - ref_len/max(hyp_len,1)) if hyp_len else 0.0)
    return {"bleu4": 100*bp*geo, "precisions": [round(100*p,2) for p in precs],
            "brevity_penalty": round(bp,4), "hyp_len": hyp_len, "ref_len": ref_len}

def rouge_l(hyps: list[str], refs: list[str]) -> float:
    """ROUGE-L F1 via longest common subsequence."""
    tot = 0.0
    for h, r in zip(hyps, refs, strict=True):
        a, b = tok(h), tok(r)
        if not a or not b: continue
        dp = [[0]*(len(b)+1) for _ in range(len(a)+1)]
        for i in range(len(a)):
            for j in range(len(b)):
                dp[i+1][j+1] = dp[i][j]+1 if a[i]==b[j] else max(dp[i][j+1], dp[i+1][j])
        lcs = dp[-1][-1]
        p, rr = lcs/len(a), lcs/len(b)
        tot += 0.0 if p+rr == 0 else 2*p*rr/(p+rr)
    return 100*tot/len(hyps) if hyps else 0.0

def template_caption(cmap, tax, syn, params, meta=None) -> str:
    """Build a factual caption from M2 attributes plus scene metadata.

    ORACLE SCOPE NOTE: the reference captions open with season, country and climate zone —
    S3 VERIFIED that the generator appends those from external maps. So an oracle that omits
    them is not measuring the symbolic ceiling, it is measuring an incomplete template. Ground-
    truth metadata is used here exactly as ground-truth MAPS are used: it is the ceiling. In the
    real system M5 predicts these, and CLAUDE.md §7 still forbids them as model INPUTS.
    """
    stats = []
    for name in tax.c19_names:
        try:
            r = extract_regions(cmap, name, "c19", tax, params)
        except Exception:
            continue
        if len(r) == 0: continue
        stats.append((r.coverage, name, len(r)))
    stats.sort(reverse=True)
    if not stats: return "The image contains no identifiable land cover."
    prim = [s for s in stats if s[0] > 0.25]
    sec  = [s for s in stats if 0.05 <= s[0] <= 0.25]
    marg = [s for s in stats if s[0] < 0.05]
    lead = "This satellite image"
    if meta:
        season, country, climate = meta
        lead += f", captured during the {str(season).lower()} in {country}"
        lead += f' within the "{str(climate).lower()}" climate zone,'
    parts = [f"{lead} shows"]
    def phrase(g): return ", ".join(f"{n.lower()} covering {100*c:.0f}% of the image in "
                                    f"{k} region{'s' if k!=1 else ''}" for c,n,k in g[:3])
    if prim: parts.append(f" mainly {phrase(prim)}.")
    if sec:  parts.append(f" It also contains {phrase(sec)}.")
    if marg:
        parts.append(" Smaller and more marginal areas of "
                     + ", ".join(n.lower() for _, n, _ in marg[:4])
                     + " are also scattered across the scene.")
    parts.append(f" In total {len(stats)} distinct land cover classes are visible in the image, "
                 f"forming {sum(k for _,_,k in stats)} separate contiguous regions.")
    return "".join(parts)

def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=260); ap.add_argument("--row-groups", type=int, default=22)
    a = ap.parse_args(argv)
    root = project_root(); cfg = load_config(); tax = load_taxonomy(); syn = load_synonyms()
    params = GeometryParams.from_config(cfg.m2, gsd_m=cfg.data.gsd_metres)
    items = []
    for fr in iter_annotations(["patch_id","output","type","country","season","climate_zone"],
                               splits=("validation",), row_groups=range(a.row_groups)):
        s = fr[fr.type == "captioning"]
        for pid, out, co, se, cl in zip(s.patch_id, s.output, s.country, s.season,
                                        s.climate_zone, strict=True):
            items.append((str(pid), str(out), (se, co, cl)))
        if len(items) >= a.n: break
    items = items[:a.n]
    print(f"caption items (validation): {len(items)}")
    hyps, refs = [], []
    for pid, ref, meta in items:
        m = TILE.search(pid)
        if not m: continue
        p = root/"data/interim/reben/reference_maps"/m.group(1)/f"{pid}.tif"
        if not p.is_file(): continue
        with rasterio.open(p) as ds: cmap = np.asarray(ds.read(1))
        hyps.append(template_caption(cmap, tax, syn, params, meta)); refs.append(ref)
    print(f"scored: {len(hyps)}\n")
    b = corpus_bleu(hyps, refs); rl = rouge_l(hyps, refs)
    print("=== O2 CAPTION ORACLE (ground-truth maps, template captions) ===")
    print(f"  BLEU-4        : {b['bleu4']:.2f}")
    print(f"  precisions    : 1g {b['precisions'][0]}  2g {b['precisions'][1]}  "
          f"3g {b['precisions'][2]}  4g {b['precisions'][3]}")
    print(f"  brevity pen.  : {b['brevity_penalty']}  (hyp {b['hyp_len']} vs ref {b['ref_len']} tokens)")
    print(f"  ROUGE-L F1    : {rl:.2f}")
    print("  METEOR/CIDEr  : NOT COMPUTED (need extra packages; BLEU-4 defines the gate)")
    print()
    v = b["bleu4"]
    verdict = ("SKIP M8 — raw templates suffice" if v >= 35 else
               "BUILD M8 — template->style rewriter" if v >= 10 else
               "DROP symbolic captioning — route to M7")
    print(f"  *** M8 GATE: BLEU-4 = {v:.2f} -> {verdict}")
    print("\n  EXAMPLE")
    print(f"    template : {hyps[0][:200]}")
    print(f"    reference: {refs[0][:200]}")
    out = root/"reports/evaluation/gate1_caption_oracle.json"
    out.write_text(json.dumps({**b, "rouge_l": round(rl,2), "n": len(hyps),
                               "m8_verdict": verdict,
                               "meteor_cider": "NOT COMPUTED"}, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
