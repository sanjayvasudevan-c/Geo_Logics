"""S8 / GATE 1 — oracle symbolic accuracy and the mandatory blind baselines.

Measures ``ORACLE(t)``: what the symbolic path scores when segmentation is *perfect*, by feeding
ground-truth CORINE reference maps into M2. Needs no GPU and no trained model.

Runs four producers over identical items, so the comparison is like-for-like:

- **oracle**       — M2 on ground-truth maps (the measurement)
- **majority**     — most frequent answer per task, learned from train
- **class_prior**  — for MCQ, the option matching the most frequent land-cover class
- **blind**        — TF-IDF + linear SVM on question text alone, **no image**

The blind baseline is mandatory (CLAUDE.md, IMPLEMENTATION_MAP §8.3). If it lands close to the
oracle for a task, that task is measuring language priors rather than perception, and saying so
is the honest result.

Evaluated on the **validation** annotation split; conventions were fitted on **train**, so this
is held out. The quarantined `bench` split is never touched.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import numpy as np
import rasterio
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

from satquery.config import load_config
from satquery.evaluation.forensics import iter_annotations
from satquery.evaluation.harness import Scored, score_task
from satquery.evaluation.oracle import OracleAnswer, ParseFailure, answer_question
from satquery.geometry import GeometryParams
from satquery.taxonomy import load_synonyms, load_taxonomy
from satquery.utils.paths import project_root

STORE = "data/interim/reben/reference_maps"
TILE = re.compile(r"_(T\d{2}[A-Z]{3})_\d+_\d+$")

GEOMETRIC = (
    "binary|presence", "binary|area", "binary|count", "binary|adjacency",
    "mcq|presence", "mcq|area", "mcq|count", "mcq|adjacency", "mcq|relative pos",
)


def load_map(root: Path, patch_id: str) -> np.ndarray | None:
    m = TILE.search(patch_id)
    if m is None:
        return None
    p = root / STORE / m.group(1) / f"{patch_id}.tif"
    if not p.is_file():
        return None
    with rasterio.open(p) as ds:
        return np.asarray(ds.read(1))


def harvest(split: str, per_task: int, row_groups: int) -> dict[str, list[tuple[str, str, str]]]:
    """Collect (patch_id, question, answer) per task type."""
    out: dict[str, list[tuple[str, str, str]]] = collections.defaultdict(list)
    for frame in iter_annotations(
        ["patch_id", "input", "output", "type", "category"],
        splits=(split,), row_groups=range(row_groups),
    ):
        for pid, q, a, t, c in zip(
            frame.patch_id, frame.input, frame.output, frame.type, frame.category, strict=True
        ):
            task = f"{t}|{c}"
            if task in GEOMETRIC and len(out[task]) < per_task:
                out[task].append((str(pid), str(q), str(a)))
        if all(len(out[t]) >= per_task for t in GEOMETRIC):
            break
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-task", type=int, default=420)
    parser.add_argument("--row-groups", type=int, default=26)
    parser.add_argument("--train-rows", type=int, default=14)
    args = parser.parse_args(argv)

    root = project_root()
    cfg = load_config()
    tax, syn = load_taxonomy(), load_synonyms()
    params = GeometryParams.from_config(cfg.m2, gsd_m=cfg.data.gsd_metres)
    print(f"Fitted conventions: connectivity={params.connectivity} "
          f"MMU={params.min_mapping_unit_px} opening={params.opening_kernel_px} "
          f"dilation={params.adjacency_dilation_px}")
    print("Evaluating on the VALIDATION split (conventions were fitted on TRAIN).\n")

    items = harvest("validation", args.per_task, args.row_groups)
    for t in GEOMETRIC:
        print(f"  {t:22s} {len(items[t]):>5,} items")
    print()

    # ---- train the blind + majority baselines on TRAIN text only -----------------------
    train = harvest("train", args.per_task * 2, args.train_rows)
    majority: dict[str, str] = {}
    blind: dict[str, tuple[TfidfVectorizer, LinearSVC]] = {}
    for t in GEOMETRIC:
        answers = [a for _, _, a in train[t]]
        if not answers:
            continue
        majority[t] = collections.Counter(answers).most_common(1)[0][0]
        if len(set(answers)) > 1:
            vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=60000)
            X = vec.fit_transform([q for _, q, _ in train[t]])
            clf = LinearSVC(C=1.0, max_iter=4000)
            clf.fit(X, answers)
            blind[t] = (vec, clf)

    # ---- run all producers over identical items ---------------------------------------
    results: dict[str, dict[str, dict]] = {}
    cache: dict[str, np.ndarray] = {}
    for t in GEOMETRIC:
        scored: dict[str, list[Scored]] = {k: [] for k in
                                           ("oracle", "majority", "blind", "class_prior")}
        blind_pred = None
        if t in blind:
            vec, clf = blind[t]
            blind_pred = clf.predict(vec.transform([q for _, q, _ in items[t]]))
        for i, (pid, q, truth) in enumerate(items[t]):
            if pid not in cache:
                m = load_map(root, pid)
                if m is None:
                    continue
                cache[pid] = m
            got = answer_question(cache[pid], q, t, tax, syn, params, cfg.m2)
            if isinstance(got, ParseFailure):
                scored["oracle"].append(
                    Scored(pid, t, None, truth, False, True, got.reason[:60])
                )
            elif isinstance(got, OracleAnswer):
                scored["oracle"].append(
                    Scored(pid, t, got.answer, truth, got.answer == truth, False)
                )
            mj = majority.get(t, "")
            scored["majority"].append(Scored(pid, t, mj, truth, mj == truth, False))
            bp = str(blind_pred[i]) if blind_pred is not None else ""
            scored["blind"].append(Scored(pid, t, bp, truth, bp == truth, False))
            cp = "a" if t.startswith("mcq") else mj
            scored["class_prior"].append(Scored(pid, t, cp, truth, cp == truth, False))
        results[t] = {k: score_task(t, v).to_dict() for k, v in scored.items() if v}

    # ---- report -------------------------------------------------------------------------
    print("=" * 92)
    print("### GATE 1 — ORACLE SYMBOLIC ACCURACY (ground-truth maps, validation split)")
    print("=" * 92)
    hdr = (f"{'task':22s} {'n':>5} {'ORACLE':>9} {'95% CI':>16} {'attempt':>9} "
           f"{'abst':>6} {'blind':>7} {'major':>7} {'gap':>7}")
    print(hdr)
    print("-" * 92)
    for t in GEOMETRIC:
        if t not in results or "oracle" not in results[t]:
            continue
        o = results[t]["oracle"]
        b = results[t].get("blind", {}).get("strict_accuracy", 0.0)
        mj = results[t].get("majority", {}).get("strict_accuracy", 0.0)
        best_blind = max(b, mj)
        print(f"{t:22s} {o['n']:>5,} {100*o['strict_accuracy']:>8.2f}% "
              f"[{100*o['ci95_low']:>5.1f},{100*o['ci95_high']:>5.1f}] "
              f"{100*o['attempted_accuracy']:>8.2f}% {100*o['abstain_rate']:>5.1f}% "
              f"{100*b:>6.2f}% {100*mj:>6.2f}% "
              f"{100*(o['strict_accuracy']-best_blind):>+6.2f}")
    print()

    geo = [results[t]["oracle"] for t in GEOMETRIC if t in results and "oracle" in results[t]]
    if geo:
        macro = sum(g["strict_accuracy"] for g in geo) / len(geo)
        macro_att = sum(g["attempted_accuracy"] for g in geo) / len(geo)
        bl = [max(results[t].get("blind", {}).get("strict_accuracy", 0.0),
                  results[t].get("majority", {}).get("strict_accuracy", 0.0))
              for t in GEOMETRIC if t in results]
        macro_blind = sum(bl) / len(bl) if bl else 0.0
        print(f"  MACRO ORACLE (strict, abstentions = wrong) : {100*macro:.2f}%")
        print(f"  MACRO ORACLE (attempted only)              : {100*macro_att:.2f}%")
        print(f"  MACRO BEST BLIND/MAJORITY BASELINE         : {100*macro_blind:.2f}%")
        print(f"  *** HEADLINE GAP (oracle - best blind)     : {100*(macro-macro_blind):+.2f} pts")
        results["_macro"] = {
            "oracle_strict": round(macro, 4), "oracle_attempted": round(macro_att, 4),
            "best_blind": round(macro_blind, 4), "gap": round(macro - macro_blind, 4),
        }

    print("\n### ABSTENTION REASONS (parser abstained rather than guessed)")
    for t in GEOMETRIC:
        if t in results and results[t]["oracle"]["abstain_reasons"]:
            print(f"  {t}:")
            for reason, n in results[t]["oracle"]["abstain_reasons"].items():
                print(f"      {n:>5,}  {reason}")

    out = root / "reports/evaluation/gate1_oracle.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
