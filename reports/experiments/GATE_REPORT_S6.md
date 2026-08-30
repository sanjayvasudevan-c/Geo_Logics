# GATE REPORT — S6 GEOGRAPHIC SPLITTING — DECISION REQUIRED

Date: 2026-08-30 · Stage: S6 · Format: CLAUDE.md §3

```
Stage:                S6 — Geographic Splitting & Leakage Detection
Metric / observation: Per-fold CORINE L3 class coverage under geographic blocking
Measured value:       20 of 44 classes absent from >=1 fold (900 maps/fold, seed 1337)
Expected / threshold: STAGE_PROMPTS.md S6 — "HALT IF rare CLC classes cannot be covered
                      across all folds under geographic blocking"
Delta vs previous:    First measurement of this quantity.
```

**Diagnosis performed:**
`[x] dataset integrity  [x] labels  [ ] preprocessing  [x] leakage  [x] split
[x] feature quality  [x] class imbalance  [x] model assumptions  [ ] hyperparameters
[ ] pipeline bug  [x] evaluation bug`

**Root-cause hypothesis:** Rare CORINE classes are geographically concentrated, and geographic
blocking separates geography by design. The two goals are in direct tension.

**Evidence supporting it — structural, not sampling:**
- Portugal has **0 patches in folds 2 and 4** (s2_tile, k=5, seed 1337).
- Every Mediterranean class absent from exactly folds 2 and 4 is Portugal-concentrated:
  212 rice-adjacent irrigation, 213 rice fields, 223 olive groves, 241, 244 agro-forestry,
  323 sclerophyllous, 522 estuaries.
- Three countries occupy a single fold each: Kosovo -> f2, Luxembourg -> f2, Switzerland -> f0.
- 335 Glaciers is absent from ALL folds, matching S4's finding that it is absent from the
  corpus entirely (43 CORINE codes + 999 observed, not 44).

**Evidence against it:** Some absences have single-digit counts (123 Port areas, 132 Dump
sites, 334 Burnt areas) and could be artifacts of the 900-maps-per-fold sample rather than truly
structural. Distinguishing them needs an exhaustive per-fold scan, which was not run.

**Consequence if unresolved:** per-fold per-class IoU is undefined for absent classes, so a
mean-over-folds mIoU is averaged over a different class set in each fold and is not comparable
across folds. This propagates directly into GATE 2's transfer factor.

**Options:**

- **A) Accept, and report per-class IoU only over folds where the class is present.**
  Cost: none. Risk: low, provided the per-class fold coverage is published alongside every
  number. Effect: honest but complicates the headline; mIoU must be qualified everywhere.

- **B) Reduce k from 5 to 3.** Cost: trivial re-run. Risk: fewer, larger folds give noisier
  fold-variance estimates, and CLAUDE.md §1 freezes k=5 — this needs a §6 change request.
  Effect: each fold spans more geography, so coverage improves; it does not eliminate the
  problem for single-country classes.

- **C) Class-aware block assignment.** Instead of packing blocks by size alone, pack them to
  balance rare-class presence across folds. Cost: a modest change to `assign_folds`. Risk:
  fold sizes become less even, and it cannot help a class confined to one tile. Effect: would
  reduce, not remove, the absences.

- **D) Report cross-fold results at coarse-7 instead of L3-44.** Cost: none. Risk: hides
  sibling-level detail, which is exactly what the benchmark's adversarial "no" answers exploit.
  Effect: coverage becomes complete at coarse-7, but the reported level no longer matches the
  segmentation target.

**Recommendation: A, with C as a cheap improvement if you want it.**
Option A is the only one that does not trade away something the architecture depends on. The
absences are a true property of the data under a discipline CLAUDE.md §1 mandates, so the
honest move is to publish per-class fold coverage next to per-class IoU and never average over
a class a fold does not contain. C is worth doing on top if the numbers matter for GATE 2, but
it cannot fix single-country classes and should not be presented as a solution.

**NOT blocked by this gate:** the leakage machinery itself is complete and passing. The
`s2_tile` strategy splits **zero** touching pairs and **zero** repeat-acquisition locations.

```
STATUS: HALTED — WAITING FOR YOUR DECISION
```
