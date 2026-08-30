# ANSWER_GRAMMAR.md — BigEarthNet.txt benchmark forensics

**Stage:** S3 · **Date:** 2026-08-30 · **Deliverable of:** STAGE_PROMPTS.md S3

> **QUARANTINE — VERIFIED, NOT ASSUMED.** Every statistic below was computed from
> `split ∈ {train, validation}` only. This was verified by an audit
> (`scripts/forensics/f00_quarantine_audit.py`), not asserted — see §0.

**STATUS: HALTED.** Three findings contradict named architectural decisions. Gate Reports are
in §12. Nothing here should be built on until those are resolved.

---

## 0. Quarantine verification (checked fact)

`scripts/forensics/f00_quarantine_audit.py` — **VERDICT: PASS**

| Check | Method | Result |
|---|---|---|
| **Static** | Scan all 7 S3 scripts for direct parquet access bypassing the filtering loader | **0 offenders**; all 7 use `iter_annotations`, 0 direct annotation reads |
| **Runtime** | Request the sealed split explicitly | **Refused** with `ContractViolationError` |
| **Runtime** | Full pass over the permitted splits | **7,128,971 rows**; distinct splits observed = `['train', 'validation']`; **bench rows observed: False** |
| **Column** | Which columns were ever read for bench rows, project-wide | **S3: none at all.** S2 (earlier stage) read `split`/`type`/`category`/`patch_id` for bench to count split sizes for the dataset card. **`input` and `output` were never read for any bench row at any point.** |

The exclusion is structural, not procedural: `satquery.evaluation.forensics.iter_annotations`
filters inside the row-group loop before yielding, and rejects `bench` if requested. 8 unit
tests cover it (`tests/unit/test_forensics_quarantine.py`).

**Every number in this document therefore comes from train+validation.** Where a per-task row
count is quoted, it is the sampled subset named in that section, not the full 7.1M.

---

## 1. Schema

Source: `f01_schema.py`, full pass, 7,128,971 train+validation rows.

| Column | Arrow type | Nulls | Null % | Cardinality | Example |
|---|---|---|---|---|---|
| `ID` | int64 | 0 | 0.000% | 273,890+ | `1966` |
| `s1_name` | string | 0 | 0.000% | 201,691+ | `S1B_IW_GRDH_1SDV_20170612T165809_33UUP_33_69` |
| `patch_id` | string | 0 | 0.000% | 201,691+ | `S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_33_69` |
| `input` | string | 0 | 0.000% | 220,840+ | `Is any broad-leaved forest and pastures side by side…` |
| `output` | string | 0 | 0.000% | 200,795+ | `yes` |
| `type` | string | 0 | 0.000% | **4** | `binary` |
| `category` | string | 0 | 0.000% | **11** | `adjacency` |
| `split` | string | 0 | 0.000% | 2 (after filtering) | `validation` |
| `latitude` | double | 0 | 0.000% | 162,433 | `47.98273012795091` |
| `longitude` | double | 0 | 0.000% | 168,299 | `12.858443091371182` |
| `country` | string | 0 | 0.000% | **10** | `Austria` |
| `season` | string | 0 | 0.000% | **4** | `Summer` |
| `climate_zone` | string | 0 | 0.000% | **10** | `Cold, no dry season, warm summer` |

**Zero nulls in every column.** `+` marks a cardinality counter capped at 200,000.

Text lengths: `input` min 29 / p50 93 / p95 223 / max 507 chars. `output` min 1 / p50 2 / p95 21
/ max 2,265 chars (the long tail is captions).

**Task space: 15 `type` × `category` combinations** (confirmed in S2 against the full table),
matching the architecture's "closed at 15 tasks".

---

## 2. CLC level actually used — **19-CLASS VOCABULARY, NOT CORINE L3**

Source: `f03_classes.py`, `f04_verify_halts.py`. 1,227,849 rows scanned.

| Measurement | Result |
|---|---|
| reBEN `metadata.parquet` `labels` vocabulary | **exactly 19 distinct classes** |
| Distinct `mcq/presence` options extracted | **19** |
| Options **inside** the 19-class set | **19 (100%)** |
| Options **outside** the 19-class set | **0** |

**Zero options fall outside the 19-class scheme.** The distribution is not "mostly 19-class with
a tail" — it is exclusively 19-class.

Apparent CLC L1/L2 hits are **substring false positives**, all resolved:

| Apparent hit | n | Actually part of |
|---|---|---|
| `wetlands` | 43,462 | "Inland wetlands" / "Coastal wetlands" (both in the 19) |
| `forests` | 81,528 | "coniferous forests" / "mixed forests" plurals |
| `sclerophyllous vegetation` | 40,659 | "Moors, heathland and sclerophyllous vegetation" |
| `sparsely vegetated areas` | 33,276 | "Natural grassland and sparsely vegetated areas" |
| `beaches` / `dunes` / `sands` | 17,258 each | "Beaches, dunes, sands" |
| `natural grasslands` | 7,578 | "Natural grassland and…" |

**No genuine CLC Level-1 group name** ("Artificial surfaces", "Agricultural areas") appears.
**No CLC Level-3 class outside the 19-class scheme** appears.

Surface variation within the 19: plurals (`arable lands`), comma removal, and
`transitional woodland, shrub` → `transitional woodlands or shrubs`.

**This is Gate Report GR-1 (§12.1).**

---

## 3. Metadata availability — **LABEL, NOT INPUT. M5 IS NOT DISCARDABLE.**

Source: `f07_metadata.py`, 695,015 rows scanned.

| Question | Evidence | Answer |
|---|---|---|
| Are country/season/climate present per row? | 0% null on all three, plus lat/lon | **Yes, present** |
| Do those columns equal the **correct MCQ answer**? | country **35,561/35,561 = 100.00%**; season **35,561/35,561 = 100.00%**; climate zone **35,562/35,562 = 100.00%** | **Yes — they are the ground-truth labels** |
| Does `country` leak into other tasks' question text? | **0 occurrences** | **No** |

**Definitive: these columns are the labels the metadata MCQs were generated from.** Using them
to answer "which country is this?" is circular label leakage, not inference. The metadata
questions must be answered from pixels.

**Therefore M5 is NOT gated away.** The architecture's discard condition ([REV §3.5]: "if the
harness supplies metadata, these become lookups → discard M5") is **not** met by the annotation
table itself.

**INCONCLUSIVE:** whether the *evaluation harness* passes these columns alongside the image at
inference time. The parquet cannot answer this — it is a property of the eval protocol, not the
data. **What would settle it:** the harness/submission specification, or an official baseline's
input signature. Until then M5 stays in scope.

*(`season_in_question_text` returned 35,562 hits. Those coincide in count with the climate-zone
MCQ block and are most likely season words inside climate-zone option strings rather than a real
leak. Not relied on; flagged as unresolved noise.)*

---

## 4. Answer grammar per task type

Source: `f02_templates.py`, 12 row groups sampled.

| type / category | rows | distinct skeletons | Answer format |
|---|---|---|---|
| `binary` / presence | 107,434 | 380 | `yes` \| `no`, lowercase, no punctuation |
| `binary` / area | 107,434 | 3,225 | `yes` \| `no` |
| `binary` / count | 107,434 | 1,008 | `yes` \| `no` |
| `binary` / adjacency | 93,693 | 4,869 | `yes` \| `no` |
| `mcq` / * (8 categories) | 39,976–53,717 each | up to 50,282 | single lowercase letter `a`\|`b`\|`c`\|`d` |
| `captioning` / None | 53,717 | **32** | free text, up to 2,265 chars |
| `bounding box` / point | 112,960 | **19** | `[x0 y0, x1 y1]` |
| `bounding box` / reference | 105,525 | 743 | `[x0 y0, x1 y1]` |

**Exact formats:**

- **Binary:** exactly two tokens, `yes` / `no`. Lowercase. No trailing punctuation. **2 distinct
  answers, confirmed.**
- **MCQ:** a single letter, lowercase, no parenthesis or period. **4 distinct answers,
  confirmed.** Options are enumerated in the question as `a) … , b) … , c) … , d) …`.
- **Bounding box:** `[x0 y0, x1 y1]` — **normalised to [0,1]**, space between the two numbers of
  a corner, comma-space between corners, square brackets. Examples: `[0.0 0.0, 1.0 1.0]`,
  `[0.35 0.0, 1.0 1.0]`. Observed precision: up to 2 decimals.
- **Referring point input:** the point is given in the question as
  `<point>(<x> <y>)</point>`; only **19 distinct question skeletons** exist for this task.
- **Referring expression input:** target wrapped in `<ref>…</ref>` tags.
- **Captioning:** free text. Only **32 distinct question skeletons**, e.g. *"Describe the
  satellite scene, including the region, time of year, and land cover classes."*

---

## 5. Numeric conventions — **AREA IS DECILE-QUANTISED**

Source: `f05_numeric.py`, 1,227,849 rows scanned.

### Area is expressed in two interchangeable units

| Task | m² values parsed | percent values parsed |
|---|---|---|
| `binary`/area | 39,691 | 78,833 |
| `mcq`/area | 74,400 | 148,916 |

Both forms occur throughout. They encode the same quantity.

### Both forms have exactly 11 distinct values

| | m² | percent |
|---|---|---|
| n | 114,091 | 227,749 |
| **distinct values** | **11** | **11** |
| min / max | 0 / **1,440,000** | 0 / 100 |
| gap between consecutive distinct values | **min = median = mode = 144,000** | 10 |
| values | 0, 144000, 288000, …, 1440000 | 0, 10, 20, …, 100 |

**1,440,000 m² = 120 px × 120 px × (10 m)² = the entire patch.** So:

```
area_m2 = percent × 14,400        and        granularity = 1 decile = 10% = 144,000 m²
```

### The "rounded to nearest 1,000 m²" convention

Technically satisfied — **100.00% of m² values are divisible by 1,000** — but **misleading**.
They are also 100.00% divisible by 10 and by 100, and the *actual* quantisation is **144,000 m²**,
which is **144× coarser** than 1,000 m². Only 26.90% are divisible by 10,000.

`configs/m2.yaml` currently carries `area_rounding_m2: 1000`. That value is 144× finer than the
data supports and encodes a convention that does not exist. **This is Gate Report GR-2 (§12.2).**

### Counts

Expressed as plain integers in words or digits. Binary count phrasings (top): `exactly two`
(12,927), `at least one` (8,791), `exactly three` (8,097), `at least four` (5,956),
`exactly four` (5,732), `fewer than three` (5,652), `fewer than two` (5,166), `exactly one`
(5,146), `more than one` (4,724), `at least two` (4,473).

---

## 6. Distractor spacing (MCQ) — **ADDITIVE IN DECILE UNITS, NOT MULTIPLICATIVE**

Source: `f05_numeric.py`, `f06_boundaries.py`, `f08_s7_residual.py`.

### Area

**MCQ area options are 100% ranges** (173,684/173,684 parsed as `X to Y`). **Zero point values.**

Gap between adjacent option lower-bounds:

| Gap (percent) | n | | Gap (m²) | n |
|---|---|---|---|---|
| 10 | 34,046 | | 144,000 | 22,559 |
| 20 | 32,682 | | 288,000 | 21,903 |
| 30 | 24,322 | | 432,000 | 16,107 |
| 40 | 16,417 | | 576,000 | 11,026 |
| 50 | 3,553 | | 720,000 | 2,436 |
| 60 | 610 | | | |
| 70 | 57 | | | |

**Every gap is an exact integer multiple of one decile.** Frequency decays with distance. The
m² column is the percent column × 14,400 — identical structure.

Option range widths: 10 (69,566), 20 (39,060), 30 (24,271), 40 (16,019) percentage points.

**The spacing is additive on an 11-point integer grid. It is not multiplicative and not
log-shaped.** M4 is specified with "log scale for areas" ([REV §3.4]) — that metric does not
match this structure. **This is Gate Report GR-3 (§12.3).**

### Count

Gap between adjacent options: 1 (99,328), 2 (39,557), 3 (14,075), 4 (2,336), 5 (3), 6 (1),
10 (2), 12 (1). **Additive in integer counts**, overwhelmingly gap-1. The architecture's "rank
scale for counts" is compatible — it reduces to integer difference.

---

## 7. Near-miss structure (binary) — **THRESHOLD COMPARISONS, NOT NEAR-MISSES**

Source: `f05_numeric.py`, `f06_boundaries.py`, `f08_s7_residual.py`.

### Question forms

`binary`/area (86,842 classified):

| Form | n | % |
|---|---|---|
| `more_than` | 28,426 | 32.7% |
| *(unmatched by regex)* | 24,022 | 27.7% |
| `between_range` | 19,047 | 21.9% |
| `at_least` | 11,028 | 12.7% |
| `at_most` | 4,319 | 5.0% |

`binary`/count (86,842 classified):

| Form | n | % |
|---|---|---|
| `at_least_n` | 25,487 | 29.3% |
| `exactly_n` | 22,315 | 25.7% |
| `at_most_n` | 17,320 | 19.9% |
| *(unmatched)* | 10,077 | 11.6% |
| `more_than_n` | 8,546 | 9.8% |
| `presence_like` | 3,097 | 3.6% |

**At least 72.3% of binary area questions and 88.4% of binary count questions are explicit
comparator or range-membership tests.** Given the true value, the answer is a deterministic
comparison. Examples verbatim:

```
Do arable lands cover at least 30% of the image?
Would you say that arable lands occupy between 0 square meters and 144000 square meters?
Do pastures occupy between 1296000 square meters and 1440000 square meters of the image?
Can you confirm that there are exactly four connected patches of arable lands in this image?
Are fewer than three continuous areas of arable lands visible here?
```

This contradicts [REV F3], which states (as VERIFIED) that "no" answers are constructed as
near-misses requiring a learned tolerance boundary. **This is Gate Report GR-4 (§12.4).**

### Measured |stated − true| for NO answers

Pairing NO answers with a YES answer on the same `(patch_id, class, category)`, n = 19,312:

| Δ (percentage points) | 0 | 10 | 20 | 30 | 40 | 50 | 60 | 70 | 80 | 90 | 100 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| n | 1,246 | 2,756 | 2,829 | 2,593 | 2,350 | 2,116 | 1,842 | 1,489 | 1,189 | 726 | 176 |

Quartiles: p25 = 20, median = 40, p75 = 60 percentage points.

**There is no tight near-miss band.** A near-miss design would concentrate mass at Δ = 10.
Instead mass is spread almost uniformly across the range and decays only at the extremes — the
shape produced by sampling a *different* decile, not by perturbing the true one.

**PARTIALLY INCONCLUSIVE.** Since 21.9% of binary area questions are range questions, my parser
took the range's lower bound as "stated", which biases Δ. **What would settle it:** compute true
coverage per 19-class from the reference maps (needs the S4 L3→19 aggregation table, which does
not exist yet) and evaluate the comparator directly rather than inferring truth from paired YES
answers. That is an S7/S8 measurement.

No count near-miss pairs were recoverable — count questions are comparator-form, so no
`(patch, class)` pair yielded a usable YES-anchored truth.

---

## 8. Adjacency phrasing

Source: `f06_boundaries.py`. Nine synonyms, by frequency:

| Phrase | n | | Phrase | n |
|---|---|---|---|---|
| `touch` | 35,042 | | `meet` | 3,136 |
| `adjacent` | 21,885 | | `neighbour` | 3,073 |
| `border` | 20,321 | | `abut` | 3,048 |
| `next to` | 15,495 | | `side by side` | 3,027 |
| `contact` | 10,949 | | | |

Templates are paraphrases of one relation: *"Is any X and Y side by side in the image?"*,
*"Does any X come into contact with Y?"*, *"Would you identify any X as lying adjacent to Y?"*

**Dilation convention: INCONCLUSIVE.** No phrasing distinguishes 4- from 8-connectivity, nor
touching from within-k-pixels. Every synonym describes the same underlying relation with no
numeric qualifier. **What would settle it:** sweep the dilation radius k ∈ {0,1,2,…} and
connectivity ∈ {4,8} against ground-truth reference maps and select the setting reproducing the
released adjacency answers exactly. That is the S7 fitting experiment and it is **unaffected by
any finding in this document**.

---

## 9. Answer priors (class-prior baseline for S8)

Source: `f06_boundaries.py`. Train+validation.

| type / category | n | Prior |
|---|---|---|
| `binary`/presence | 124,076 | yes **50.0%** / no **50.0%** |
| `binary`/area | 124,076 | yes **50.0%** / no **50.0%** |
| `binary`/count | 124,076 | no **50.0%** / yes **50.0%** |
| `binary`/adjacency | 108,672 | **no 57.1% / yes 42.9%** |
| `mcq`/presence | 62,037 | a 25.3, b 24.9, c 25.0, d 24.8 |
| `mcq`/area | 62,037 | a 25.0, b 25.2, c 24.8, d 25.0 |
| `mcq`/count | 62,037 | a 25.0, b 25.2, c 24.9, d 24.9 |
| `mcq`/adjacency | 46,633 | a 25.2, b 24.7, c 25.1, d 25.0 |
| `mcq`/relative pos | 11,718 | a 24.9, b 25.0, c 24.8, d 25.3 |
| `mcq`/country | 62,037 | a 24.8, b 25.2, c 25.1, d 24.9 |
| `mcq`/season | 62,037 | a 25.3, b 24.6, c 25.0, d 25.1 |
| `mcq`/climate zone | 62,037 | a 25.0, b 24.7, c 25.0, d 25.3 |

**Three of four binary sub-tasks are balanced to 50.0/50.0. All eight MCQ sub-tasks are balanced
to within 0.7 points of 25%.** The majority-class baseline is therefore ≈50% for binary and ≈25%
for MCQ — a system must clearly exceed these to demonstrate perception.

**`binary`/adjacency is the one imbalance: 57.1% no.** A majority-class baseline scores **57.1%**
there — which is *above* the 55.86% a reported-2T-parameter model achieves on adjacency
(PUBLISHED, IMPLEMENTATION_MAP Appendix A). **Answering "no" to every adjacency question beats
that published frontier-model score.** This must be reported at S8 and S16; it materially
reframes the headline adjacency comparison.

---

## 10. Referring-expression qualifiers

Source: `f06_boundaries.py`. Extracted from `<ref>` tags.

| Qualifier | n |
|---|---|
| *(none — bare class name)* | 66,586 |
| `largest patch` | 7,360 |
| `largest continuous area` | 7,313 |
| `largest contiguous area` | 7,246 |
| `smallest patch` | 6,543 |
| `largest connected region` | 4,838 |
| `largest continuous region` | 4,812 |
| `smallest contiguous area` | 4,810 |
| `smallest continuous area` | 3,262 |
| `smallest connected region` | 3,244 |
| `largest connected patch` | 2,430 |
| `smallest continuous region` | 1,564 |
| `smallest contiguous region` | 1,545 |
| `smallest continuous patch` | 1,531 |

**The semantic vocabulary is exactly two operators — `largest` and `smallest` — crossed with
eight surface phrasings** (`patch`, `continuous area`, `contiguous area`, `connected region`,
`continuous region`, `connected patch`, `contiguous region`, `continuous patch`). No directional
qualifiers (`north-most`, `left-most`) were observed in `<ref>` tags.

The 262 distinct raw `<ref>` strings are compositional: {∅, largest, smallest} × {8 phrasings} ×
{19 classes}. Roughly 55% of referring expressions carry no qualifier at all and target the class
generically.

**Note:** directional language *does* appear, but in `mcq`/relative pos, not referring
expressions — options there are `to the left`, `to the right`, `to the bottom`, etc.

---

## 11. What this means for each downstream component

| Component | Impact | Gate |
|---|---|---|
| **M1** | Predicting at CORINE L3 (44) remains viable, but every question is asked at the 19-class level. The auxiliary 19-class head is on the query path, not auxiliary. | GR-1 |
| **M2** | Needs an **L3(44) → 19** aggregation table, not an L1/L2/L3 CLC-hierarchy table. Area needs exact coverage + range membership, not 1,000 m² rounding. Connectivity/MMU/opening/dilation fitting is **unaffected**. | GR-1, GR-2 |
| **M3** | ≥72% of area and ≥88% of count questions are deterministic comparisons. A learned tolerance boundary may be unnecessary. | GR-4 |
| **M4** | Area distance must operate on an additive 11-point decile grid, not a log scale. | GR-3 |
| **M5** | **Not discardable.** Metadata is the label, not an input. | — |
| **M9** | Unaffected. | — |
| **S8 baselines** | Majority baseline = 50% binary / 25% MCQ, except adjacency at **57.1%**. | — |

---

## 12. GATE REPORTS

Four contradictions of named architectural decisions. **Per CLAUDE.md §3 and §6, work is halted
until these are resolved. They are not absorbed into this document as settled facts.**

Full text: **[`reports/experiments/GATE_REPORT_S3.md`](../../reports/experiments/GATE_REPORT_S3.md)**

| ID | Contradiction | Affects |
|---|---|---|
| **GR-1** | Questions use the **19-class vocabulary**, not CORINE L3. CLAUDE.md §1 says the 19-class scheme is "image-level multi-label only, NOT the segmentation target". | M1 head, M2 aggregation table, S4 |
| **GR-2** | Area is **decile-quantised** (11 bins, 144,000 m² granularity), not continuous-rounded-to-1,000 m². `configs/m2.yaml` `area_rounding_m2: 1000` is 144× too fine. | M2, S7 fitting |
| **GR-3** | MCQ distractor spacing is **additive on a decile grid**, contradicting M4's specified **log-scale** area distance. | M4 |
| **GR-4** | Binary questions are **deterministic threshold/range comparisons**, contradicting [REV F3]'s VERIFIED claim that NO answers are near-misses needing a learned M3 boundary. | M3 |

---

## Appendix — Analysis code paths

| Script | Items | Output |
|---|---|---|
| `scripts/forensics/f00_quarantine_audit.py` | quarantine | `f00_quarantine_audit.json` |
| `scripts/forensics/f01_schema.py` | 1 | `f01_schema.json` |
| `scripts/forensics/f02_templates.py` | 4, 8, 10 | `f02_templates.json` |
| `scripts/forensics/f03_classes.py` | 2 | `f03_classes.json` |
| `scripts/forensics/f04_verify_halts.py` | 2, 5 | `f04_halts.json` |
| `scripts/forensics/f05_numeric.py` | 5, 6 | `f05_numeric.json` |
| `scripts/forensics/f06_boundaries.py` | 6, 7, 9, 10 | `f06_boundaries.json` |
| `scripts/forensics/f07_metadata.py` | 3 | `f07_metadata.json` |
| `scripts/forensics/f08_s7_residual.py` | 5, 7 follow-up | `f08_s7_residual.json` |

Outputs in `reports/experiments/forensics/`. Narrative in
`reports/experiments/benchmark_forensics.md`.
