# GATE 1 — Oracle Symbolic Accuracy

**Stage:** S8 · **Date:** 2026-08-30 · **STATUS: HALTED — decision required**

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

### `mcq|relative pos` — 65.33%. **Convention error, not geometry.**

0% abstention, so these are genuinely wrong answers rather than declined ones.
Diagnosis found and fixed a real bug: the option matcher compared a *single compass
letter as a substring*, so a computed `SE` matched the option "bottom-left" because
`"S" in "SE"`. Compound-first exact matching with an angular-nearest fallback moved
it **55.33% -> 65.33%**.

The residual is a genuine **unfitted convention**: the generator resolves diagonals
differently from a centroid-offset 8-way compass. Observed case — computed `SW` with
options {E, NE, W, S}, where `S` and `W` are exactly equidistant and the generator
chose `S`. **S7 fitted connectivity, MMU, opening and dilation but never the direction
rule.** It is a fittable parameter that nobody has fitted yet.

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