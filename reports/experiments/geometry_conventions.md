# M2 Convention Fitting — S7

**Date:** 2026-08-30 · **Split:** training annotations only (CLAUDE.md §7) · **Seed:** 1337
**Sample:** 1,000 items per sweep, **stratified across all 5 folds**, 20 parquet row groups

## Method — and two obligations inherited from earlier stages

**Supervision comes from MCQ, not binary.** S3 established that binary questions are
comparator-form ("at least N", "fewer than three"), which gives only indirect supervision. MCQ
gives *direct* labels: for `mcq|count` the correct option's integer **is** the true region
count; for `mcq|area` the correct option's range **contains** the true coverage. That turns
fitting from an inference problem into a lookup.

**Obligation 1 — S3 GR-2** deferred the area bin-boundary convention to this stage, to be
confirmed against computed ground truth rather than swept blindly. Done; see §3. The answer is
a non-result, reported as such.

**Obligation 2 — S6 GATE-2 propagation** requires per-class scoring over each class's own valid
fold set. Every table below reports **per-class accuracy** (mean of per-class rates) alongside
the pooled rate. Pooling would weight a class by how often it happens to be asked about — the
same averaging error S6 removed at the fold level.

> **A first attempt failed this obligation and was redone.** Taking the first N matching items
> drew them all from **fold 0**, which would have fitted a convention on one region's geography.
> A per-fold quota fixed it; the tables below span folds 0–4.

---

## 1. Connectivity and minimum mapping unit

`mcq|count`, n = 1,000 across 13 classes and all 5 folds.

| connectivity | MMU (px) | **per-class acc** | pooled acc |
|---|---|---|---|
| **4** | **0** | **100.00%** | **100.00%** |
| 4 | 1 | 100.00% | 100.00% |
| 4 | 2 | 96.66% | 97.80% |
| 4 | 4 | 95.27% | 95.90% |
| 4 | 8 | 93.53% | 94.10% |
| 4 | 16 | 91.16% | 90.90% |
| 4 | 32 | 85.93% | 86.70% |
| 8 | 0 | 98.50% | 99.00% |
| 8 | 1 | 98.50% | 99.00% |
| 8 | 2 | 96.61% | 97.70% |
| 8 | 4 | 95.22% | 95.80% |
| 8 | 8 | 93.49% | 94.00% |
| 8 | 16 | 91.16% | 90.90% |
| 8 | 32 | 85.93% | 86.70% |

**FITTED: connectivity = 4, MMU = 0. Margin over 8-connectivity: +1.50 points.**

**100.00% is the signal the architecture predicted:** *"If a setting reproduces them at 100%,
you have recovered the generator's convention and that is free accuracy for the rest of the
project."* The generator used `scipy.ndimage.label` with 4-connectivity and no MMU filtering.

**Any MMU above 1 strictly hurts** — monotonically, from 96.66% at 2 px down to 85.93% at 32 px.
The architecture anticipated MMU as a tunable defence against fragmentation; on ground-truth
maps it is pure damage, because there is nothing to defend against. MMU 0 and 1 are equivalent
(no component has zero pixels). **This may change at S17**, where the same parameters are
re-fitted against *predicted* maps, which do fragment.

---

## 2. Adjacency dilation radius

`binary|adjacency`, n = 1,000, fold-stratified.

| k (px) | **per-class acc** | pooled acc |
|---|---|---|
| 0 | 64.55% | 59.20% |
| **1** | **97.62%** | **98.00%** |
| 2 | 97.27% | 97.80% |
| 3 | 97.27% | 97.80% |
| 5 | 97.03% | 97.50% |

**FITTED: k = 1.**

k = 0 is bare mask intersection and collapses to 64.55%, so **dilation is genuinely required** —
"adjacent" means *touching*, not *overlapping*. k = 1 is the peak; k = 2 and 3 are within 0.35
points, so the choice between them is not strongly discriminated, and k = 1 is the parsimonious
pick. S8 measured that a majority-class baseline on adjacency scores 57.1%, so 97.62% is a
genuine result rather than a prior being echoed back.

---

## 3. Area bin-boundary rule — **UNDER-DETERMINED, not fitted**

S3 GR-2 deferred this here. The honest answer is that **the data cannot distinguish the
candidates.**

| rule | per-class acc | pooled acc |
|---|---|---|
| `inclusive_lower_exclusive_upper` | 99.9000% | 99.8000% |
| `inclusive_both` | 99.9000% | 99.8000% |
| `exclusive_lower_inclusive_upper` | 99.9000% | 99.8000% |

**All three are identical to four decimal places on n = 1,000.** Not a tie to be broken — the
boundary case essentially never occurs. Coverage is an exact float and the bins are 10
percentage points wide, so landing precisely on an edge has vanishing probability.

**Consequence:** `bin_boundary_rule` is set to `inclusive_lower_exclusive_upper` as the standard
convention, **for definiteness only**. It is *not* a measurement, and **no result may be
attributed to this choice.** If a future analysis appears sensitive to it, that sensitivity is
itself a bug worth investigating.

This closes S3 GR-2's condition: the convention was *checked against computed ground truth*, and
the check returned "immaterial" rather than a value. That is a legitimate outcome, and a more
useful one than a fitted number that was actually arbitrary.

---

## 4. Values written to `configs/m2.yaml`

```yaml
connectivity: 4              # 100.00% per-class; +1.50 pts over 8-connectivity
min_mapping_unit_px: 0       # any MMU > 1 strictly hurts on ground-truth maps
opening_kernel_px: 0         # the generator applies no morphological cleanup
adjacency_dilation_px: 1     # 97.62%; k=0 collapses to 64.55%
bin_boundary_rule: inclusive_lower_exclusive_upper   # UNDER-DETERMINED, convention only
```

## 5. Caveats

- Sample is 1,000 items per sweep, fold-stratified but not exhaustive. The 100.00% count result
  is strong, but on 1,000 items a true rate of 99.7% would plausibly show as 100%.
- Fitted on **ground-truth** maps. IMPLEMENTATION_MAP §6.2 requires a **second fit against
  predicted maps at S17**, because the optimal cleanup for a noisy map is not the optimal
  cleanup for a clean one. MMU = 0 is very likely to change there.
- 13 of 19 classes appear in the count sample; rare classes are under-represented, consistent
  with the irreducible coverage limits recorded in `DECISIONS.md` L-S6-2.
