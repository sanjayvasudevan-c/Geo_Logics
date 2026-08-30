"""S9 — measure Q1 rule-parser coverage and precision, then fit and score the M10 fallback.

Four numbers the stage requires, plus the honest limitation list:

1. **Rule coverage** — % of questions parsed at all, per task. Abstention is not failure; it is
   the parser declining to guess, and it is what makes the residue diagnosable.
2. **Rule precision** — on parsed questions, does the extracted intent match the annotation's
   own ``(type, category)``? This is the number that matters. A parser can reach 100% coverage
   by guessing and be worthless.
3. **M10 accuracy on the residue only** — the questions the rules declined. Fitted on train,
   scored on validation.
4. **Combined coverage**, and the unparsed residue with real examples.

Fitting and training use the **training** split; all reported accuracy is on **validation**.
The quarantined ``bench`` split is never touched.

The HALT condition from the stage prompt is checked explicitly and printed either way: if rule
coverage is low enough that M10 becomes the primary path rather than a fallback, that inverts
the architecture's intent and is a decision, not an implementation detail.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys

from satquery.evaluation.forensics import iter_annotations
from satquery.routing import (
    Intent,
    M10Classifier,
    ParseFailure,
    QuerySpec,
    parse_query,
    task_to_intent,
)
from satquery.taxonomy import load_synonyms
from satquery.utils.paths import project_root

#: The stage prompt's HALT condition, made numeric so it cannot be waved through.
#: M10 is a FALLBACK. If the rules cover less than this, it is the primary path instead.
RULE_COVERAGE_FLOOR = 0.50


def harvest(split: str, per_task: int, row_groups: int, *, skip: int = 0
            ) -> list[tuple[str, str, str, Intent]]:
    """Collect (question, type, category, true_intent), quota'd per task.

    Args:
        split: Annotation split. Never ``bench`` — the loader refuses it.
        per_task: How many items to keep per ``(type, category)``.
        row_groups: How many parquet row groups to scan.
        skip: Discard this many items per task before collecting. Used to carve a slice that
            development never saw — see ``--holdout-skip``.
    """
    out: list[tuple[str, str, str, Intent]] = []
    seen: collections.Counter[tuple[str, str]] = collections.Counter()
    kept: collections.Counter[tuple[str, str]] = collections.Counter()
    for frame in iter_annotations(
        ["input", "type", "category"], splits=(split,), row_groups=range(row_groups),
    ):
        for q, t, c in zip(frame.input, frame.type, frame.category, strict=True):
            key = (str(t), str(c))
            seen[key] += 1
            if seen[key] <= skip or kept[key] >= per_task:
                continue
            kept[key] += 1
            out.append((str(q), key[0], key[1], task_to_intent(*key)))
        if len(kept) >= 15 and all(v >= per_task for v in kept.values()):
            break
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-task", type=int, default=400)
    ap.add_argument("--row-groups", type=int, default=30)
    ap.add_argument(
        "--holdout-skip", type=int, default=0,
        help="Skip this many items per task before sampling. The rules were developed by "
             "inspecting errors on the first slice of validation, which makes that slice "
             "DEVELOPMENT data. Passing a skip larger than the development sample carves a "
             "genuinely untouched slice; that is the number to quote.")
    args = ap.parse_args(argv)

    root = project_root()
    syn = load_synonyms()
    print("Q1 parser evaluated on VALIDATION; M10 fitted on TRAIN. `bench` never touched.")
    if args.holdout_skip:
        print(f"*** HELD-OUT MODE: skipping the first {args.holdout_skip:,} items per task, "
              f"which development saw. This slice was never inspected. ***")
    else:
        print("*** DEVELOPMENT SLICE — rule errors here were inspected while writing the "
              "rules, so these numbers are OPTIMISTIC. Re-run with --holdout-skip. ***")
    print()

    val = harvest("validation", args.per_task, args.row_groups, skip=args.holdout_skip)
    print(f"### validation items: {len(val):,} over "
          f"{len({(t, c) for _, t, c, _ in val})} tasks\n")

    # ---------------------------------------------------- 1 + 2. coverage and precision -----
    per_task: dict[tuple[str, str], dict[str, int]] = collections.defaultdict(
        lambda: {"n": 0, "parsed": 0, "correct": 0})
    reasons: collections.Counter[str] = collections.Counter()
    residue: list[tuple[str, str, str, Intent]] = []
    confusion: collections.Counter[tuple[str, str]] = collections.Counter()
    examples: dict[str, list[str]] = collections.defaultdict(list)

    for q, t, c, truth in val:
        rec = per_task[(t, c)]
        rec["n"] += 1
        got = parse_query(q, syn)
        if isinstance(got, ParseFailure):
            reasons[got.reason] += 1
            residue.append((q, t, c, truth))
            if len(examples[got.reason]) < 3:
                examples[got.reason].append(q[:160])
            continue
        assert isinstance(got, QuerySpec)
        rec["parsed"] += 1
        ok = got.intent is truth
        rec["correct"] += int(ok)
        confusion[(truth.value, got.intent.value)] += 1

    print("### 1-2. RULE-PARSER COVERAGE AND PRECISION, per task")
    print(f"{'type':<14}{'category':<15}{'n':>6}{'coverage':>11}{'precision':>11}{'end-to-end':>12}")
    print("-" * 69)
    rows = []
    for (t, c), r in sorted(per_task.items()):
        cov = r["parsed"] / r["n"]
        prec = r["correct"] / r["parsed"] if r["parsed"] else 0.0
        e2e = r["correct"] / r["n"]
        rows.append({"type": t, "category": c, "n": r["n"], "coverage": round(cov, 4),
                     "precision": round(prec, 4), "end_to_end": round(e2e, 4)})
        print(f"{t:<14}{c:<15}{r['n']:>6}{100*cov:>10.2f}%{100*prec:>10.2f}%{100*e2e:>11.2f}%")

    tot_n = sum(r["n"] for r in per_task.values())
    tot_p = sum(r["parsed"] for r in per_task.values())
    tot_c = sum(r["correct"] for r in per_task.values())
    macro_cov = sum(r["coverage"] for r in rows) / len(rows)
    macro_prec = sum(r["precision"] for r in rows) / len(rows)
    print(f"\n  POOLED   coverage {100*tot_p/tot_n:.2f}%   precision {100*tot_c/max(tot_p,1):.2f}%"
          f"   end-to-end {100*tot_c/tot_n:.2f}%")
    print(f"  MACRO    coverage {100*macro_cov:.2f}%   precision {100*macro_prec:.2f}%")

    # ---------------------------------------------------- 3. M10 on the residue only --------
    print(f"\n### 3. M10 FALLBACK — fitted on TRAIN, scored on the {len(residue):,} "
          f"validation questions the rules DECLINED")
    train = harvest("train", args.per_task * 2, args.row_groups)
    all_q = [q for q, _, _, _ in train]
    all_y = [t for _, _, _, t in train]
    res_q = [q for q, _, _, _ in train if isinstance(parse_query(q, syn), ParseFailure)]
    res_y = [t for q, _, _, t in train if isinstance(parse_query(q, syn), ParseFailure)]
    print(f"    train pool: all {len(all_q):,} questions "
          f"({len({y.value for y in all_y})} intents) | "
          f"rules-residue only {len(res_q):,} ({len({y.value for y in res_y})} intents)")

    # WHICH POOL? The intuitive choice is residue-only: M10 only ever sees residue at
    # inference, so train it on that. Measured, that is WRONG here — the rules are good enough
    # that the residue holds too few items and too few distinct intents to span the label
    # space, so a residue-fitted M10 cannot even emit most intents. Fitting on all training
    # questions keeps the full 9-way label space available. Both are measured below rather than
    # argued about.
    m10_block: dict[str, object] = {
        "n_train_all": len(all_q), "n_train_residue": len(res_q),
        "n_train_residue_intents": len({y.value for y in res_y}),
        "n_eval_residue": len(residue),
    }
    if residue:
        for pool_name, pq, py in (("residue_only", res_q, res_y), ("all_train", all_q, all_y)):
            if len(pq) < 20 or len({y.value for y in py}) < 2:
                print(f"    pool {pool_name}: NOT FITTABLE "
                      f"({len(pq)} items, {len({y.value for y in py})} intents)")
                m10_block[f"{pool_name}_fittable"] = False
                continue
            probe = M10Classifier.fit(pq, py)
            pr = probe.predict([q for q, _, _, _ in residue])
            h = sum(1 for p, t in zip(pr, [t for _, _, _, t in residue], strict=True) if p is t)
            print(f"    pool {pool_name:<13} labels={len(probe.labels)}  "
                  f"accuracy on residue {100*h/len(residue):.2f}%  ({h}/{len(residue)})")
            m10_block[f"{pool_name}_accuracy"] = round(h / len(residue), 4)
            m10_block[f"{pool_name}_n_labels"] = len(probe.labels)

    tr_q, tr_y = all_q, all_y
    if len(tr_q) >= 20 and len({y.value for y in tr_y}) >= 2 and residue:
        m10 = M10Classifier.fit(tr_q, tr_y)
        pred = m10.predict([q for q, _, _, _ in residue])
        truths = [t for _, _, _, t in residue]
        hits = sum(1 for p, t in zip(pred, truths, strict=True) if p is t)
        acc = hits / len(residue)
        per_lbl: dict[str, dict[str, int]] = collections.defaultdict(
            lambda: {"tp": 0, "fp": 0, "fn": 0})
        for p, t in zip(pred, truths, strict=True):
            if p is t:
                per_lbl[t.value]["tp"] += 1
            else:
                per_lbl[t.value]["fn"] += 1
                per_lbl[p.value]["fp"] += 1
        f1s = []
        print(f"    M10 accuracy on residue: {100*acc:.2f}%  ({hits:,}/{len(residue):,})")
        print(f"\n    {'intent':<20}{'tp':>6}{'fp':>6}{'fn':>6}{'F1':>9}")
        for lbl, v in sorted(per_lbl.items()):
            p_ = v["tp"] / max(v["tp"] + v["fp"], 1)
            r_ = v["tp"] / max(v["tp"] + v["fn"], 1)
            f1 = 2 * p_ * r_ / (p_ + r_) if (p_ + r_) else 0.0
            f1s.append(f1)
            print(f"    {lbl:<20}{v['tp']:>6}{v['fp']:>6}{v['fn']:>6}{100*f1:>8.2f}%")
        macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
        print(f"    MACRO-F1: {100*macro_f1:.2f}%")

        # --- DUPLICATE-LEAKAGE SPLIT (CLAUDE.md §7) -------------------------------------
        # S3 measured only ~220k distinct `input` strings across 7.1M rows, so questions
        # repeat heavily and train/validation share verbatim text. An accuracy computed over
        # both halves together is partly a memorisation score. Reporting them apart is the
        # only honest way to quote this number.
        seen_text = set(tr_q)
        idx_seen = [i for i, (q, _, _, _) in enumerate(residue) if q in seen_text]
        idx_new = [i for i in range(len(residue)) if i not in set(idx_seen)]
        acc_seen = (sum(1 for i in idx_seen if pred[i] is truths[i]) / len(idx_seen)
                    if idx_seen else None)
        acc_new = (sum(1 for i in idx_new if pred[i] is truths[i]) / len(idx_new)
                   if idx_new else None)
        print("\n    *** duplicate-leakage split ***")
        print(f"    verbatim-in-train  : {len(idx_seen):>5,} items "
              f"({100*len(idx_seen)/len(residue):5.2f}%)  accuracy "
              f"{'n/a' if acc_seen is None else f'{100*acc_seen:.2f}%'}")
        print(f"    UNSEEN TEXT        : {len(idx_new):>5,} items "
              f"({100*len(idx_new)/len(residue):5.2f}%)  accuracy "
              f"{'n/a' if acc_new is None else f'{100*acc_new:.2f}%'}  <-- the honest number")

        m10_block |= {"accuracy": round(acc, 4), "macro_f1": round(macro_f1, 4),
                      "labels": list(m10.labels), "manifest": m10.manifest,
                      "n_verbatim_in_train": len(idx_seen), "n_unseen_text": len(idx_new),
                      "accuracy_verbatim": None if acc_seen is None else round(acc_seen, 4),
                      "accuracy_unseen_text": None if acc_new is None else round(acc_new, 4)}
        out_model = root / "models/m10/m10_intent_svm.joblib"
        m10.save(out_model)
        print(f"    persisted -> {out_model}")

        # ------------------------------------------------ 4. combined ----------------------
        combined = (tot_c + hits) / tot_n
        print(f"\n### 4. COMBINED  rules-correct {tot_c:,} + M10-correct {hits:,} "
              f"of {tot_n:,} = {100*combined:.2f}%")
        m10_block["combined_intent_accuracy"] = round(combined, 4)
    else:
        print("    NOT FITTED — insufficient residue or only one intent in it. "
              "That is itself the result: the rules left too little for a fallback to learn.")

    # ---------------------------------------------------- residue, honestly -----------------
    print(f"\n### 5. UNPARSED RESIDUE — {len(residue):,}/{tot_n:,} "
          f"({100*len(residue)/tot_n:.2f}%). The honest limitation list.")
    for reason, n in reasons.most_common():
        print(f"\n  {n:>5,}  {reason}")
        for ex in examples[reason]:
            print(f"           e.g. {ex}")

    residue_by_task = collections.Counter((t, c) for _, t, c, _ in residue)
    if residue_by_task:
        print("\n  residue by task:")
        for (t, c), n in residue_by_task.most_common():
            print(f"    {t:<14}{c:<15}{n:>6,}  ({100*n/per_task[(t, c)]['n']:.1f}% of that task)")

    # ---------------------------------------------------- the HALT check --------------------
    pooled_cov = tot_p / tot_n
    print("\n### 6. HALT CHECK (stage prompt): is M10 the fallback or the primary path?")
    print(f"    rule coverage {100*pooled_cov:.2f}%  vs floor {100*RULE_COVERAGE_FLOOR:.0f}%")
    halted = pooled_cov < RULE_COVERAGE_FLOOR
    print("    *** HALT — rules are not the primary path. Decision required. ***" if halted
          else "    PASS — the rules are the primary path and M10 is a genuine fallback.")

    result = {
        "per_task": rows,
        "pooled": {"coverage": round(pooled_cov, 4),
                   "precision": round(tot_c / max(tot_p, 1), 4),
                   "end_to_end": round(tot_c / tot_n, 4), "n": tot_n},
        "macro": {"coverage": round(macro_cov, 4), "precision": round(macro_prec, 4)},
        "m10": m10_block,
        "residue_reasons": dict(reasons.most_common()),
        "residue_examples": {k: v for k, v in examples.items()},
        "residue_by_task": {f"{t}|{c}": n for (t, c), n in residue_by_task.items()},
        "confusion": {f"{a}->{b}": n for (a, b), n in confusion.items() if a != b},
        "halt": halted, "rule_coverage_floor": RULE_COVERAGE_FLOOR,
    }
    out = root / "reports/experiments/s9_parser.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
