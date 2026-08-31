# GATE 1 — Oracle Symbolic Accuracy

**Stage:** S8 + S7 addendum · **Date:** 2026-08-30 · **STATUS: GATE 1 PASSED**

> Sections 1-6 are the **original Gate 1 measurement**, on which the PASS verdict
> was given. They are deliberately left as measured. **§7 is the addendum** that
> fitted the one convention S7 had left uncalibrated; it shows before and after
> side by side rather than replacing the original numbers.

Measures `ORACLE(t)` in `TARGET(t) = ORACLE(t) x TRANSFER(t)`: what the symbolic path
scores when segmentation is **perfect**. Ground-truth CORINE maps fed into M2. No GPU,
no trained model. Conventions were fitted on **train** (S7) and evaluated here on
**validation**. The quarantined `bench` split was never touched.

---

## 1. Headline

| | |
|---|---|
| **MACRO ORACLE** (strict, abstentions = wrong) | **87.11%** |
| MACRO ORACLE (attempted only) | 93.89% |
| MACRO best blind / majority baseline | 49.07% |
| **HEADLINE GAP** | **+38.04 points** |

The 6.78-point gap between strict and attempted accuracy is **entirely
parser abstention**, not geometry error. Those are S9's to fix and are the cheapest
points available in the project.

## 2. Per task

| task | n | **ORACLE** | 95% CI | attempted | abstain | blind | majority | gap vs best |
|---|---|---|---|---|---|---|---|---|
| `binary|presence` | 300 | **100.00%** | [100.0, 100.0] | 100.00% | 0.0% | 82.67% | 50.00% | **+17.33** |
| `binary|area` | 300 | **74.33%** | [69.3, 79.3] | 94.49% | 21.3% | 61.00% | 50.00% | **+13.33** |
| `binary|count` | 300 | **91.00%** | [86.7, 94.7] | 98.20% | 7.3% | 72.33% | 50.00% | **+18.67** |
| `binary|adjacency` | 300 | **95.67%** | [93.3, 97.7] | 97.95% | 2.3% | 72.33% | 50.00% | **+23.34** |
| `mcq|presence` | 300 | **90.67%** | [87.3, 94.0] | 90.67% | 0.0% | 46.67% | 26.67% | **+44.00** |
| `mcq|area` | 300 | **88.67%** | [85.3, 92.3] | 100.00% | 11.3% | 23.33% | 26.67% | **+62.00** |
| `mcq|count` | 300 | **100.00%** | [100.0, 100.0] | 100.00% | 0.0% | 21.67% | 29.00% | **+71.00** |
| `mcq|adjacency` | 300 | **78.33%** | [73.0, 83.0] | 98.33% | 20.3% | 26.33% | 22.67% | **+52.00** |
| `mcq|relative pos` | 300 | **65.33%** | [59.7, 71.0] | 65.33% | 0.0% | 24.67% | 24.33% | **+40.66** |

Confidence intervals are bootstrap over **patches**, not annotations — several
questions share one image, so resampling annotations independently would understate
them (IMPLEMENTATION_MAP §8.3).

## 3. Diagnosis of every task below ~90%

### `mcq|relative pos` — **RESOLVED at the S7 addendum. See §7.**

Measured at **65.33%** in the original Gate 1 run and diagnosed there as a
convention error rather than a geometry error, because abstention was 0%. That
diagnosis was correct: fitting the convention moved it to **92.67%** 
(**+27.34** points) with no change to the geometry engine's
measurement code. The original number is preserved throughout this report.

### `binary|area` — 74.33% strict / 94.49% attempted. **Parser error.**

21.3% abstention: 24 'no threshold', 24 'no comparator', 16 'no class resolved'. The
geometry is sound at 94.49% on attempted items; the parser does not cover every
phrasing. S9 territory.

### `mcq|adjacency` — 78.33% strict / 98.33% attempted. **Parser error.**

20.3% abstention, every one 'no MCQ option yielded two classes'. **98.33% on attempted**
says the adjacency geometry is essentially correct; the option-pair splitter is not.

### `mcq|presence` — 90.67%, 0% abstention. Mild class-resolution error.

## 4. Where the blind baseline is uncomfortably strong

**`binary|presence`: blind = 82.67%** against an oracle of
100.00%.

A TF-IDF + linear SVM on **question text alone, with no image**, answers four in five
presence questions correctly. The class name is highly predictive of the answer: common
classes are usually present, rare ones usually absent.

**This must be stated plainly to judges.** For binary presence, most of the achievable
score is available without looking at the image. The symbolic path still wins by
+17.33 points and is perfect — but quoting 100%
without 82.67% beside it would overstate what was demonstrated. This is the same
discipline already recorded for adjacency in DECISIONS.md.

By contrast the MCQ tasks are **not** language-guessable: blind scores 21-47% against
oracles of 65-100%, gaps of +30 to +71 points. That is where the architecture's central
claim is doing real work.

## 5. O2 — caption oracle and the M8 gate

| metric | value |
|---|---|
| **BLEU-4** | **15.35** |
| precisions (1-4 gram) | 54.9, 32.81, 25.0, 21.22 |
| brevity penalty | 0.4911 (18,190 vs 31,126 tokens) |
| ROUGE-L F1 | 33.87 |
| METEOR / CIDEr | NOT COMPUTED |

**M8 GATE: BLEU-4 = 15.35 -> BUILD M8 — template->style rewriter**, the 10-35 band the
architecture predicted it would land in.

**A first run scored 2.60 and would have said 'drop symbolic captioning'. That was an
artifact, not a finding.** The brevity penalty was 0.1205: the template ran 3x short and
omitted the season / country / climate-zone opening that S3 VERIFIED the generator
appends. Including it took BLEU-4 to 15.35 and flipped the verdict.

**15.35 remains a LOWER bound.** The brevity penalty is still 0.4911
(18,190 vs 31,126 tokens), so a richer template scores higher.

**Oracle scope note:** the caption oracle uses ground-truth metadata exactly as it uses
ground-truth maps — both are the ceiling. In the deployed system M5 predicts those
fields, and CLAUDE.md §7 still forbids them as model *inputs*.

## 6. Caveats

- 300 items per task, 220 captions. At n=300 a true 95% would plausibly read 93-97%.
- Metadata MCQ (country / season / climate) is **excluded** — not geometry-derived, so
  outside the oracle's scope. That measurement belongs to M5, gated at S15.
- Referring expression and referring point were **NOT MEASURED**: they need IoU against
  released boxes rather than exact match, which this harness does not yet score.
- METEOR and CIDEr not computed (additional packages). BLEU-4 defines the gate.

---

## 7. ADDENDUM — the direction convention, fitted

**Added after the Gate 1 decision, at the reviewer's direction.** Gate 1 verdict
PASS was recorded against the numbers in §1-§6 above; nothing there is restated
to look better than it was measured. The one component S7 left uncalibrated has
since been fitted, and this section reports what that changed.

### 7.1 Before / after

Same protocol, same validation split, same 300 items per task. Only the
relative-position convention differs.

| task | before | after | delta |
|---|---|---|---|
| `binary|presence` | 100.00% | 100.00% | +0.00 |
| `binary|area` | 74.33% | 74.33% | +0.00 |
| `binary|count` | 91.00% | 91.00% | +0.00 |
| `binary|adjacency` | 95.67% | 95.67% | +0.00 |
| `mcq|presence` | 90.67% | 90.67% | +0.00 |
| `mcq|area` | 88.67% | 88.67% | +0.00 |
| `mcq|count` | 100.00% | 100.00% | +0.00 |
| `mcq|adjacency` | 78.33% | 78.33% | +0.00 |
| `mcq|relative pos` | 65.33% | **92.67%** | **+27.34** |
| **MACRO (strict)** | 87.11% | **90.15%** | **+3.04** |
| **MACRO (attempted)** | 93.89% | **96.92%** | **+3.03** |
| **HEADLINE GAP** | +38.04 | **+41.07** | **+3.03** |

**Attribution is clean: exactly 1 of 9 tasks moved**
(`mcq|relative pos`). The other 8 are
bit-identical, so the macro gain is attributable to the convention and to nothing
else. The blind baseline is unchanged at 49.07%, as it must be — no baseline was re-fitted.

The macro number moved because one task moved a long way, not because nine tasks
each drifted up a little. Read §7.1 by the row, not by the bottom line.

### 7.2 What was measured, and what was not

Fitted on **train** only, all 5 folds, scored per class-pair over each pair's own
valid fold set (S6 GATE-2 propagation). Evaluated on **validation**, above.

**MEASURED — decisive:**

- Template family `ref_first` (511 items) **inverts subject and
  reference**: read as written it scores 0.00%, flipped 87.10%.
- Template family `from_to` (138 items) **inverts subject and
  reference**: read as written it scores 0.00%, flipped 91.25%.

  The 0.00% is not a coincidence and should not be quoted as a dramatic finding:
  exact-matching a reversed bearing selects the option 180 degrees from the truth
  whenever it is offered, so the reversed reading *cannot* be accidentally right.
  It does mean the error was total on 25.96% of items, which is why this single
  fix dominates the delta.

- The textbook equal-sector 8-way compass is **wrong**. A 45-degree diagonal band
  scores 87.01% against 93.57% for a narrow one. Corroborating this independently:
  released answers are cardinal 81.60% of the time while cardinals are
  only ~62% of the offered options.

**UNDER-DETERMINED — a non-result, exactly as `bin_boundary_rule` was:**

- The exact band inside roughly [10, 22] degrees is **not resolvable**. McNemar
  exact tests over 2,500 items separate no candidate from any other (best
  p = 0.068). The shipped value, 16 degrees, is the one point where two *independent*
  lines of evidence converge — it lies inside the accuracy plateau and it
  reproduces the observed diagonal-answer rate, a statistic the accuracy sweep
  never optimised for. It is **not** the accuracy argmax, which was
  bbox_centre at 12 degrees and is 0.39 pts higher and
  statistically indistinguishable. No result should be attributed to 16 over 14.
- The reference-point rule is under-determined in the strongest possible sense:
  `mask_centroid` and `largest_component` differ in *position* on 263 of 2,500
  items and change **zero** predicted answers. `mask_centroid` is shipped on two
  non-accuracy grounds — it is the same "a class is its mask" semantics
  `compute_area` and `compute_count` already use, and the centre of a union
  bounding box is maximally sensitive to one stray pixel, which is the wrong
  statistic once S13 feeds M2 *predicted* maps instead of ground truth.

### 7.3 Per-fold stability

| fold | n | before | after | delta |
|---|---|---|---|---|
| 0 | 500 | 64.32% | 93.25% | +28.93 |
| 1 | 500 | 64.03% | 96.48% | +32.45 |
| 2 | 500 | 74.35% | 95.71% | +21.36 |
| 3 | 500 | 63.73% | 96.86% | +33.13 |
| 4 | 500 | 61.63% | 94.50% | +32.87 |

Improves in **5/5 folds** (min +21.36, max +33.13) — not a single-region artifact.

### 7.4 Residual — measured, not guessed

`mcq|relative pos` sits at 92.67% with **0% abstention**,
so the remainder are still wrong answers rather than declined ones. Train-split
accuracy under the fitted convention is 93.57% per class-pair, so validation tracks train
and this is the convention's ceiling rather than an overfit that failed to
transfer.

The obvious guess is that one template family is still mis-parsed. **It is not.**
Per-family accuracy under the fitted convention:

| template family | n | accuracy | errors | share of residual |
|---|---|---|---|---|
| `subject_first` | 1,727 | 94.56% | 94 | 69.6% |
| `ref_first` | 511 | 93.74% | 32 | 23.7% |
| `from_to` | 138 | 97.10% | 4 | 3.0% |
| `between` | 124 | 95.97% | 5 | 3.7% |

All four families land within 93.74%-97.10%, and each
family's share of the residual tracks its share of the items. The orientation
question is therefore **fully resolved**; what remains is borderline-angle error
distributed evenly, which is what an under-determined band width predicts. No
further convention is claimed, and none is available to fit without more evidence.

---

## 8. ADDENDUM 2 — a shared config moved this number without anyone re-running it

**This section exists because the drift was caught, not because it was planned.**
`configs/synonyms.yaml` is used by both the S9 Q1 parser and the S8 oracle. S9
added two missing surface forms for the *parser's* benefit — a plural class name
and a singular one. Those also improved the *oracle's* class resolution, and this
gate moved with nothing failing and no gate run.

| | after S7 addendum | after S9 | delta |
|---|---|---|---|
| `binary|presence` | 100.00% | 100.00% | +0.00 |
| `binary|area` | 74.33% | **78.33%** | **+4.00** |
| `binary|count` | 91.00% | **97.00%** | **+6.00** |
| `binary|adjacency` | 95.67% | **98.00%** | **+2.33** |
| `mcq|presence` | 90.67% | 90.67% | +0.00 |
| `mcq|area` | 88.67% | **100.00%** | **+11.33** |
| `mcq|count` | 100.00% | 100.00% | +0.00 |
| `mcq|adjacency` | 78.33% | 78.33% | +0.00 |
| `mcq|relative pos` | 92.67% | 92.67% | +0.00 |
| **MACRO (strict)** | 90.15% | **92.78%** | **+2.63** |
| **HEADLINE GAP** | +41.07 | **+43.70** | **+2.63** |
| **abstention gap** | 6.77 | **4.15** | **-2.62** |

The cause is understood and legitimate — better class resolution, no leakage, no
change to any geometry or scoring code. `configs/synonyms.yaml` was the **only**
fingerprinted file the S9 commit touched.

**What was actually wrong was the process, not the number.** A metric report is a
claim about a specific configuration, and this one did not record which. So:

- `satquery/evaluation/provenance.py` fingerprints every config that can move a
  measured number, and `run_oracle.py` stamps it into the artifact.
- This measurement's fingerprint: `e4dd82df6b4f309f`.
- `tests/unit/test_gate_provenance.py` **fails** if a recorded gate stops matching
  the working tree, and carries a guard proving it can still fire.

The Gate 1 verdict was PASS on 87.11%. It has since been measured at 90.15% and
now 92.78%, each time for an understood reason. **Nothing here re-litigates the
verdict** — the number has only ever moved up.