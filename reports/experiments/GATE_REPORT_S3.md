# GATE REPORT — S3 BENCHMARK FORENSICS — DECISION REQUIRED

Date: 2026-08-30 · Stage: S3 · Format: CLAUDE.md §3, with §6 change-control blocks for GR-3/GR-4

Four findings contradict named architectural decisions. Combined into one report because they
share a single root cause (see §0) and are best decided together.

**All evidence from `train`+`validation` only; quarantine verified PASS — ANSWER_GRAMMAR.md §0.**

---

## 0. Root cause — one fact explains all four

The architecture's answer-grammar assumptions were inherited from the *captioning* pipeline
described in arXiv:2603.29630 §3.1 — where areas are continuous values rounded to 1,000 m² and
"no" answers are near-misses. **The VQA/MCQ annotations do not follow that pipeline.** They are
generated on a coarse **11-point decile grid over the 19-class vocabulary**, with answers
produced by deterministic comparators.

The caption path may still match the original description — caption answers do contain
`square_metres` (42,036 hits) and `thousand_m2` (41,987 hits) patterns. **Captions were not
analysed in depth at S3** and may retain the finer convention. That is an open question, not a
resolved one.

So the architecture is not *wrong* so much as **generalised from the wrong task family**.

---

## GR-1 — Questions use the 19-class vocabulary, not CORINE Level-3

```
Stage:                S3
Metric / observation: Class vocabulary used by benchmark questions
Measured value:       19/19 mcq/presence options inside the reBEN 19-class set; 0 outside
Expected / threshold: CLAUDE.md §1 — "19-class vocabulary: image-level multi-label only.
                      NOT the segmentation target." Questions were expected to span the
                      CLC L1/L2/L3 hierarchy (REV F1).
Delta vs previous:    First measurement of this quantity.
```

**Diagnosis performed:**
`[x] dataset integrity  [x] labels  [ ] preprocessing  [ ] leakage  [x] split
[x] feature quality  [ ] class imbalance  [x] model assumptions  [ ] hyperparameters
[ ] pipeline bug  [x] evaluation bug`

**Root-cause hypothesis:** BigEarthNet.txt generates questions from reBEN's 19-class
*image-level* vocabulary, not from the CORINE L3 pixel reference maps' 44-class nomenclature.

**Evidence supporting it:**
- 19 distinct `mcq/presence` options; **all 19 inside the 19-class set; 0 outside** (1,227,849 rows).
- No CLC L1 group name appears anywhere.
- Every apparent L2/L3 hit resolved to a substring of a 19-class name (table in §2 of ANSWER_GRAMMAR).
- `<ref>` vocabulary decomposes as {∅, largest, smallest} × {8 phrasings} × {19 classes}.

**Evidence against it:** None found. The reference maps genuinely carry 44 L3 codes (S2: 43 CORINE
codes + `999`), so L3 supervision exists — it is simply not the level questions are asked at.

**Options:**
- **A) Keep M1 at L3-44, add an L3→19 aggregation table.** Cost: the S4 taxonomy table becomes
  L3→19 instead of L1/L2/L3 (same effort, different target). Risk: low. Expected effect: preserves
  the architecture's "predict fine, aggregate at query time" principle; the aux 19-class head
  moves onto the query path.
- **B) Retrain M1 directly at 19 classes.** Cost: contradicts CLAUDE.md §1's frozen taxonomy.
  Risk: high — discards sibling-level detail the hierarchy-aware loss targets, and the 44-class
  reference maps are the actual supervision available. Expected effect: simpler, weaker.
- **C) Predict L3-44, but report and evaluate only at 19.** Cost: none beyond A. Risk: low.
  Expected effect: same as A, plus mIoU@44 stays a diagnostic rather than a headline.

**Recommendation: A (with C's reporting stance).** It is the smallest change, keeps CLAUDE.md §1's
frozen 44-class target intact, and the aggregation step already exists in the design as "M2 step 0".
The only edit is the aggregation table's *target*, plus promoting the 19-class head from auxiliary
to query-critical.

---

## GR-2 — Area is decile-quantised; the 1,000 m² rounding convention does not exist

```
Stage:                S3
Metric / observation: Area quantisation granularity
Measured value:       11 distinct values; gap min=median=mode=144,000 m² (=10% of patch);
                      max 1,440,000 m² = the whole 120x120 patch
Expected / threshold: configs/m2.yaml area_rounding_m2 = 1000; REV §3.2 lists area rounding as
                      "VERIFIED, no fitting needed" at nearest 1,000 m²
Delta vs previous:    Actual granularity is 144x coarser than configured
```

**Diagnosis performed:**
`[x] dataset integrity  [x] labels  [x] preprocessing  [ ] leakage  [x] split
[x] feature quality  [ ] class imbalance  [x] model assumptions  [ ] hyperparameters
[ ] pipeline bug  [x] evaluation bug`

**Root-cause hypothesis:** Area answers are bucketed into deciles of patch coverage before being
templated. The m² form is the percent form × 14,400 and carries no additional precision.

**Evidence supporting it:**
- m²: n=114,091, **11 distinct values**, gaps uniformly 144,000.
- percent: n=227,749, **11 distinct values**, exactly 0,10,…,100.
- 100.00% of m² values divisible by 1,000 — but also by 10 and 100; only 26.90% by 10,000.
- MCQ area options are **100% ranges** (173,684/173,684), never point values.

**Evidence against it:** The 1,000 m² claim is *technically* true (all values are divisible by
1,000), so the architecture is not factually wrong — only 144× more precise than the data warrants.
Caption answers may still use the finer convention (not analysed).

### Your question: does this make S7's rounding-parameter sweep moot?

**Partly. One of five fitted parameters becomes moot; a different one replaces it; three are
untouched.**

| S7 fitted parameter | Status after GR-2 |
|---|---|
| `area_rounding_m2` | **MOOT.** Nothing is rounded. Compute exact fractional coverage, then test range membership. No sweep. |
| **NEW: decile boundary inclusivity** | **STILL FITTABLE, and it matters.** 68.2% of adjacent MCQ area ranges **share an endpoint** (e.g. `0 to 10%` and `10 to 20%`). At exactly 10% the correct option is ambiguous without knowing the convention. Sweep ⌊·⌋ / round-half-up / ⌈· ⌉ and inclusive/exclusive bounds against released answers. |
| `connectivity` (4 vs 8) | **UNAFFECTED.** Count-only. Still the highest-value sweep. |
| `min_mapping_unit_px` | **UNAFFECTED** for count. **Newly relevant to area** via assumption A6 — does coverage include MMU-dropped components? |
| `opening_kernel_px` | **UNAFFECTED.** Count-only. |
| `adjacency_dilation_px` | **UNAFFECTED.** §8 shows phrasing gives no hint; the sweep remains the only way to recover it. |

**Net: S7 remains necessary and its highest-value experiments are unchanged.** The area sweep
changes character from "find the rounding granularity" to "find the bin-boundary convention",
which is a smaller search over a discrete set.

**Options:**
- **A) Set `area_rounding_m2: null`, add `area_bins: 11` and a fitted `bin_boundary_rule`.**
  Cost: a config edit and a small S7 sweep. Risk: low. Expected effect: M2 computes exact
  coverage and answers by range membership.
- **B) Keep 1,000 m² rounding.** Cost: none now. Risk: it is a no-op that implies false precision
  and will mislead anyone reading the config. Expected effect: harmless but dishonest.

**Recommendation: A.**

---

## GR-3 — M4's distance metric

**This is a change to a named model. CLAUDE.md §6 format:**

```
=== PROPOSED ARCHITECTURE CHANGE ===

Original (with architecture doc section reference):
  REV §3.4 / IMPLEMENTATION_MAP §4 — M4 MCQ option scorer: "distance-based selection in a
  FITTED METRIC. Not naive absolute distance — for areas the right scale is log, for counts
  it is rank. Formally a 4-way softmax over -d(computed, option_k)/T, with d and T fitted."
  CLAUDE.md §1 — "M4: Fitted distance (log for area, rank for count) + softmax."

Problem observed:
  Area options are not point values on a continuous scale. They are RANGES on an 11-point
  decile grid, and distractor spacing is additive in decile units.

Evidence (measured, not assumed):
  - MCQ area options: 173,684/173,684 = 100% ranges, 0 point values.
  - Adjacent-option gaps are exact multiples of one decile:
      percent  10:34,046  20:32,682  30:24,322  40:16,417  50:3,553  60:610  70:57
      m2      144k:22,559 288k:21,903 432k:16,107 576k:11,026 720k:2,436
  - Only 11 distinct area values exist in the entire train+val annotation set.
  - Count option gaps are additive integers: 1:99,328  2:39,557  3:14,075  4:2,336.

Proposed replacement:
  AREA:  containment test first — select the option whose [lo, hi] range contains the computed
         coverage. Fall back to |decile_index difference| when no range contains it (possible
         only if options are gapped, which occurs in 31.8% of items). No log transform.
  COUNT: |integer difference|, which is what "rank scale" reduces to on this data. Effectively
         unchanged from the architecture.
  Retain the softmax over -d/T with T fitted, so M4 still emits a calibrated distribution
  for M9. Only the metric d changes.

Expected benefit:
  A log metric on an 11-point grid distorts distances near 0% (log 0 undefined; 0% occurs and
  is a valid option bound). Containment is exact where it applies, which is 68.2%+ of items.
  It also makes M4 auditable: "computed 34% coverage falls in option c) 30 to 40%".

Risk:
  Low. The change is strictly simpler and removes an undefined-at-zero edge case. Residual
  risk is the boundary convention at shared endpoints, which is GR-2's fitted parameter --
  the two must be decided together.

Testing required to validate:
  Fit on train, evaluate option-selection accuracy on validation, comparing three metrics:
  (i) containment + decile-index fallback, (ii) log distance as specified, (iii) linear
  absolute distance. Report all three. Scheduled for S14 (M4), using ground-truth areas
  from S8's oracle so that M1 error does not confound the metric comparison.

DECISION: WAITING FOR APPROVAL
```

---

## GR-4 — M3's decision boundary

**This is a change to a named model. CLAUDE.md §6 format:**

```
=== PROPOSED ARCHITECTURE CHANGE ===

Original (with architecture doc section reference):
  REV F3 (marked VERIFIED) — "for count and size questions, 'no' answers are constructed so
  that the queried class is present but the stated quantity is wrong. So answering is not
  computed == stated. It is: given my estimate, my uncertainty, and the generator's near-miss
  distribution, is the stated value inside the acceptance region? That is a binary decision
  under uncertainty with an empirically-determined boundary. It should be an explicit trained
  model."
  CLAUDE.md §1 — "M3: Binary YES/NO head. LightGBM (~200 trees, depth 4) or L2 logistic."

Problem observed:
  The majority of binary area and count questions are explicit comparator or range-membership
  tests. Given a true value, the answer is a deterministic comparison, not a decision under
  uncertainty about a hidden acceptance region.

Evidence (measured, not assumed):
  binary/area  (n=86,842):  more_than 32.7%, between_range 21.9%, at_least 12.7%,
                            at_most 5.0%  => >=72.3% explicitly comparative
  binary/count (n=86,842):  at_least 29.3%, exactly 25.7%, at_most 19.9%, more_than 9.8%,
                            presence_like 3.6%  => >=88.4% explicitly comparative
  Verbatim: "Do arable lands cover at least 30% of the image?"
            "Do pastures occupy between 1296000 and 1440000 square meters of the image?"
            "Are fewer than three continuous areas of arable lands visible here?"
  Measured |stated - true| for NO answers (n=19,312) is near-uniform across deltas
  (p25=20, median=40, p75=60 percentage points) -- NOT the concentrated band a near-miss
  generator would produce.

Proposed replacement:
  Two-path M3.
    PATH 1 -- DETERMINISTIC (>=72% area, >=88% count): parse (comparator, operand) from the
      question, compute the quantity in M2, evaluate the comparison, return yes/no. No model.
      Fully auditable; the trace shows the literal comparison performed.
    PATH 2 -- LEARNED (the residual: unparsed forms, and any genuinely equality-shaped item):
      retain the specified LightGBM/logistic head with the specified feature set.
  M3 keeps its interface and still emits P(yes) for M9 -- Path 1 emits a calibrated-by-
  construction probability derived from M1 uncertainty propagated through the comparison,
  rather than a point 0/1.

Expected benefit:
  Removes a learned approximation of an exactly known rule from >=72% of the traffic.
  Eliminates the risk of M3 learning the training set's comparator mix rather than the
  comparison itself. Improves auditability, which is a stated architectural requirement.

Risk:
  MEDIUM, and I want to flag it honestly. The deterministic path is only as good as the
  question parser: a comparator misparse silently flips an answer, with no learned model to
  absorb it. 27.7% of area and 11.6% of count questions were NOT matched by my regex -- these
  may be further comparator phrasings, or genuine equality items. Until they are classified,
  the true deterministic share is a lower bound.
  Mitigation: Path 2 is the fallback for anything the parser does not confidently classify,
  and the parser must abstain rather than guess.

Testing required to validate:
  1. Classify the 27.7% / 11.6% unmatched forms (S3 follow-up, ~1 hour, no model needed).
  2. On ground-truth maps at S8, measure oracle accuracy of the deterministic path per
     comparator form. If it is not ~100%, the parser or the comparison is wrong, not the model.
  3. At S14, compare deterministic-only, learned-only, and hybrid on validation.

DECISION: WAITING FOR APPROVAL
```

---

## STATUS

```
STATUS: HALTED — WAITING FOR YOUR DECISION
```

**Not blocked by these gates** (may proceed once you decide): S7's connectivity, MMU, opening
kernel and adjacency dilation sweeps are unaffected by all four findings.

**Blocked by these gates:** S4 (taxonomy table target — GR-1), the `configs/m2.yaml` area
parameters (GR-2), M4's metric (GR-3), M3's structure (GR-4).

**Recommended immediate follow-up regardless of decision:** classify the 27.7% unmatched binary
area forms and the 11.6% unmatched count forms. It is cheap, needs no model, and it converts
GR-4's evidence from a lower bound into an exact share.
