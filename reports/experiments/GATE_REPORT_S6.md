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

---

## RESOLUTION — stratified allocation reached the irreducible floor

**The original analysis conflated two independent degrees of freedom.** Block *integrity*
(no block spans folds — non-negotiable, settled) and block *assignment* (which fold a whole
block joins — a free choice). Size-balanced packing optimised fold balance and nothing else, so
a region's classes clustered into a few folds as a pure artifact of packing order. Geography
forces that no tile spans folds; it does **not** force which fold a tile joins.

Option C was therefore tested before falling back to Option A.

| Allocation | classes absent | irreducible | **artifact** | fold balance | touching pairs split |
|---|---|---|---|---|---|
| size-balanced | 17 | 14 | **3** — 132, 141, 421 | 0.991 | 0 of 419,356 |
| **stratified** | **14** | 14 | **0** | 0.954 | 0 of 419,356 |
| *theoretical floor* | *14* | *14* | *0* | — | — |

**Stratified allocation removes every removable absence and reaches the floor exactly.** The
leakage guarantee is unchanged — zero touching pairs split under both. Cost is fold balance
0.991 → 0.954, which is acceptable.

### Why the residual 14 are provably irreducible

Blocks are atomic, so **a class present in fewer than k=5 tiles cannot appear in all 5 folds
under any allocation whatsoever.** Counting tiles per class settles it arithmetically rather
than by argument:

```
123 Port areas (3 tiles)        124 Airports (3)            212 Perm. irrigated land (3)
213 Rice fields (3)             223 Olive groves (3)        241 Annual+permanent crops (3)
244 Agro-forestry (3)           323 Sclerophyllous veg (3)  334 Burnt areas (4)
335 Glaciers (0 — absent)       422 Salines (2)             423 Intertidal flats (4)
521 Coastal lagoons (3)         522 Estuaries (2)
```

Most are single-growing-region Mediterranean crops concentrated in Portugal. This is now a
**checked** result, not an assumed one — which is what makes Option A defensible.

**Measurement caveat:** per-tile presence was sampled at 140 maps/tile, which undercounts tiles
holding very rare classes. The irreducible set is an **upper bound**; an exhaustive scan could
move a class from irreducible to reducible, never the reverse.

### Final decision

- **FINAL SPLIT:** `data/processed/splits/FINAL_s2_tile_stratified_k5_seed1337.json`
- **Option A applies to the residual 14 only**, and its reporting discipline stands:
  1. per-class IoU reported **only over folds containing the class**;
  2. per-class fold coverage published **beside every number**;
  3. mean-over-folds mIoU **not comparable** across classes with different fold-presence sets.
- **k=5 unchanged. No collapse to coarse-7.** Both were rejected as quiet architecture changes
  disguised as workarounds — see `docs/architecture/DECISIONS.md` D-S6-2.

### Propagation — binding before S13 starts

**The transfer factor at GATE 2 must be computed per class over each class's own valid fold
set, not as a single pooled number**, because the fold-presence set differs per class. Recorded
in `PROJECT_STATUS.md` and `docs/architecture/DECISIONS.md` L-S6-2.

```
STATUS: RESOLVED — stratified allocation adopted; Option A covers the proven residual
```
