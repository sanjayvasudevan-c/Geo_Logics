# SatQuery — Claude Code Stage Prompts

27 stages (S0–S26). Paste **one stage at a time**. Copy everything between the
`▶ START` and `◀ END` markers.

---

## HOW TO USE THIS

**Before S0 — one-time setup:**

1. Create the repo folder and `cd` into it.
2. Copy `CLAUDE.md` into the repo root. Claude Code reads it automatically every session, so the
   standing rules apply to every stage without re-pasting.
3. Put the architecture PDF at `docs/architecture/SatQuery_Architecture.pdf`.
4. Start Claude Code in that folder.

**Per stage:**

1. Paste the stage prompt.
2. Let it build, test, and report.
3. If it emits a **GATE REPORT** → it has stopped on purpose. Read it, decide, reply with your
   decision. Do not paste the next stage until the gate is resolved.
4. If it emits a **TRAINING RUNBOOK** → you run the training on your GPU/Colab, then paste the
   real metrics back. Do not let it proceed on imagined numbers.
5. When the stage reports `STAGE <n> COMPLETE`, paste the next stage.

**Gate stages (expect to be stopped):** S8, S13, S16, S23.
**Human-training stages (expect a runbook):** S12, S15, S17, S19, S20, S23.

**If you ever suspect drift**, paste this one-liner:

> Re-read `CLAUDE.md` §1 (Frozen Architecture Facts) and audit the last stage's code against it.
> Report every contradiction. Do not fix anything until I approve the list.

---

# STAGE 0 — Architecture Ingestion & Implementation Map (NO CODE)

▶ START

You are the Lead AI/ML Architect for SatQuery. Read `CLAUDE.md` first, then read the full
architecture document at `docs/architecture/SatQuery_Architecture.pdf`. That document is the
primary source of truth.

**DO NOT WRITE ANY IMPLEMENTATION CODE IN THIS STAGE.** Output analysis only.

Produce the following, in this order:

**1. COMPLETE ARCHITECTURE UNDERSTANDING**
Explain the whole system in your own words: the 9 stages, the perception/measurement/language
separation, and why the architecture predicts a map and then calculates the answer instead of
asking a VLM. State explicitly why the benchmark's own construction (answers derived from
pixel-level reference maps) is the justification for this design.

**2. COMPLETE COMPONENT INVENTORY**
Every layer, stage, task type, model (M1–M10), validator (V1), parser (Q1), router (R1), dataset,
service, evaluation component, and security component. For each: one-line purpose.

**3. END-TO-END DATA FLOW**
Trace all seven query families separately — area, count, presence, adjacency, relative position,
referring expression/point, metadata MCQ, caption, change — from GeoTIFF + question through to
JSON + evidence + trace. Show exactly which components fire for each and which stay idle.

**4. MODEL & DATASET MATRIX**
Table: Component | Model/Method | Dataset | Input (shape/type) | Output (shape/type) | Metric |
Training strategy | Purpose.

**5. DEPENDENCY & ERROR-PROPAGATION MAP**
Which components depend on which. Where an upstream error becomes an unrecoverable downstream
error. Mark each component `DETERMINISTIC` or `PROBABILISTIC`.

**6. IMPLEMENTATION PLAN**
The exact build order, with the reasoning for that order (notably: why the geometry engine and
oracle experiment come *before* training M1).

**7. TESTING PLAN**
Per component: unit, integration, data, model, pipeline, API, e2e, regression, edge-case.

**8. ACCURACY IMPROVEMENT PLAN**
How accuracy will be improved without compromising evaluation integrity. Must be built around
`TARGET(t) = ORACLE(t) × TRANSFER(t)`, not around guessed targets.

**9. RISK REGISTER**
Technical, data, model, security, integration, performance, and demonstration risks. For each:
likelihood, impact, early-warning signal, mitigation.

**10. ASSUMPTIONS & AMBIGUITIES**
Everything in the architecture that is underspecified or must be validated against the real data.
Mark each `ASSUMPTION — REQUIRES VALIDATION`. Be specific — this list drives Stage 3.

**11. DEFINITION OF DONE**
Exact conditions that must hold before we call this SIH-ready.

Write the result to `docs/architecture/IMPLEMENTATION_MAP.md`. Create `PROJECT_STATUS.md` using
the format in `CLAUDE.md` §10. Then stop.

◀ END

---

# STAGE 1 — Layer 0: Project Foundation

▶ START

Read `CLAUDE.md` and `docs/architecture/IMPLEMENTATION_MAP.md`.

Build the project skeleton. No ML logic in this stage — only the foundation everything else sits on.

**BUILD:**

1. **Repository structure** — `src/` split into `data/`, `preprocessing/`, `taxonomy/`,
   `geometry/`, `models/`, `routing/`, `inference/`, `evaluation/`, `api/`, `security/`, `utils/`;
   plus `configs/`, `tests/{unit,integration,model,api,e2e}/`, `scripts/`, `data/{raw,interim,processed}/`,
   `models/`, `reports/{experiments,evaluation,error_analysis}/`, `docs/{architecture,datasets,experiments,security}/`,
   `notebooks/exploration/`.
2. **Dependency management** — `pyproject.toml` with pinned versions. Core: rasterio, numpy, scipy,
   scikit-image, scikit-learn, torch, torchvision, pydantic, pyyaml, pandas, pyarrow, lightgbm,
   pytest, structlog (or equivalent). Do not add anything not yet justified.
3. **Configuration management** — hierarchical YAML in `configs/` (`data.yaml`, `preprocessing.yaml`,
   `taxonomy.yaml`, `m1.yaml`, `m2.yaml`, ... , `eval.yaml`), loaded through one typed
   `Config` object validated with Pydantic. No parameter may be hardcoded in `src/`.
4. **Structured logging** — JSON logs, run ID, stage name, component name. A redaction filter that
   prevents secrets and file paths outside the project from being logged.
5. **Exception hierarchy** — `SatQueryError` base, with `InputValidationError`, `TaxonomyError`,
   `GeometryError`, `RoutingError`, `ModelError`, `ContractViolationError`. Typed errors only;
   no bare `except:`.
6. **Reproducibility utilities** — `set_global_seed(seed)` covering random/numpy/torch/CUDA;
   `capture_environment()` recording python version, package versions, git commit, GPU, seed;
   `hash_file()` and `hash_config()` helpers.
7. **Artifact/run registry** — every run writes `reports/runs/<run_id>/` containing config snapshot,
   environment capture, seed, git commit, metrics, and logs.
8. **Secrets management** — `.env.example` only; `python-dotenv` loading; `.gitignore` covering
   `.env`, `data/`, `models/`, checkpoints. No secret ever in source.
9. **Testing framework** — pytest with markers `unit`, `integration`, `slow`, `gpu`, `benchmark`;
   coverage config; a `make test` target.
10. **CI-style checks** — `make lint` (ruff), `make typecheck` (mypy on `src/`), `make test`.
11. **`README.md`** — what the project is, how to set it up, how to run tests, the stage map.

**TESTS TO WRITE AND RUN NOW:**
- config loads and validates; invalid config raises a typed error
- seeding is deterministic (same seed → same random draws across all three libraries)
- logger redacts a planted fake secret
- every exception type is constructible and carries context
- environment capture returns a complete non-empty record

**DELIVERABLES:** working skeleton, all tests green, `PROJECT_STATUS.md` updated.

**CONSTRAINTS:** no ML code, no dataset download, no placeholder functions that silently return
dummy values — if a function is not implemented yet, it raises `NotImplementedError`.

Show me the real `pytest` output. Then stop.

◀ END

---

# STAGE 2 — Dataset Acquisition, Licence Audit & Storage Plan

▶ START

Read `CLAUDE.md` §7 (Data Discipline).

Acquire and register the datasets the architecture specifies. **Do not substitute datasets.**

**DATASETS (architecture-specified):**

| Dataset | Role | Expected figures from architecture |
|---|---|---|
| BigEarthNet v2 / reBEN | M1 supervision (S1 + S2 + CORINE L3 reference maps) | 549,488 pairs; filtered 464,044; train 229,114 / val 118,095 / test 116,835 |
| BigEarthNet.txt | Answer grammar: captions, binary VQA, MCQ, referring | ~9.6M annotations; benchmark split 1,082 pairs / 15,029 annotations |
| SECOND | M6 semantic change | 2,968 public pairs, 6 classes |
| CDVQA | Change VQA benchmark | 65,967 QA / 1,600 train pairs; 16,441 val QA / 400 val pairs; 19 answer categories |
| VRSBench | Evaluation + scale robustness only | 29,614 images; 52,472 REs; 123,221 QA |
| RSVQA | Evaluation only, never training | — |

**BUILD:**

1. **Download scripts** in `scripts/data/` — resumable, checksum-verified, idempotent. Each logs
   exactly what it fetched and its size.
2. **Storage plan** — reBEN is very large. Before downloading anything, compute the total disk
   requirement and report it to me. Propose a development strategy: a **stratified subset** for fast
   iteration (stratified by country and by CLC L3 class presence, geographically blocked, seed
   recorded) plus the full set for final training. Document the subset construction so it is
   reproducible. Flag clearly that all headline results must eventually come from the full split,
   not the subset.
3. **Integrity verification** — per dataset: file count, checksum manifest, corrupt-file scan,
   readable-by-rasterio scan on a sample.
4. **Licence audit** → `docs/datasets/LICENCE_AUDIT.md`: each dataset's licence, whether
   redistribution is allowed, whether commercial/hackathon demonstration use is allowed, required
   attribution text. Flag anything that restricts what we can show judges.
5. **Dataset cards** → `docs/datasets/<name>.md` per `CLAUDE.md` §7.
6. **Verification against architecture figures** — count actual samples and splits, and compare
   against the table above. If your real counts differ from the architecture's stated figures,
   **do not adjust the code to match either number silently** — report the discrepancy.
7. **Quarantine guard** — implement the benchmark-split loader so it raises unless the environment
   variable `ALLOW_BENCHMARK_EVAL=1` is explicitly set. Write a test proving it raises by default.

**TESTS:** integrity checks pass; quarantine guard raises by default; dataset cards exist for every
dataset; sample GeoTIFFs open with rasterio and report expected band counts.

**HALT IF:** a dataset is unavailable, licence-restricted, gated behind an application, or its real
sample counts contradict the architecture. Emit a Gate Report and stop.

Report real counts and real disk usage. Then stop.

◀ END

---

# STAGE 3 — Benchmark Forensics → `ANSWER_GRAMMAR.md`

▶ START

Read `CLAUDE.md`. This is the single most important investigative stage in the project. Everything
downstream — M2's fitted conventions, M3's decision boundary, M4's distance metric, whether M5 is
needed at all — depends on what you find here.

The architecture says: **inspect the benchmark parquet in week 1 before deciding anything.**

**INVESTIGATE (read-only; use the train/val annotation splits, NOT the quarantined benchmark split):**

1. **Schema** — dump the full parquet/annotation schema: every column, dtype, null rate,
   cardinality, example values.
2. **CLC level actually used** — determine empirically which CORINE level the questions reference.
   Do they name L3 classes, L2 groups, L1 groups, or a mixture? Quantify the distribution.
3. **Metadata availability** — is country, acquisition date, and geolocation present in the
   benchmark input? This decides the M5 gate. Report a definitive yes/no with evidence.
4. **Answer grammar per task type** — for binary VQA, MCQ, captions, referring expressions,
   referring points: exact answer formats, allowed vocabularies, units, casing, punctuation.
5. **Numeric conventions** — rounding granularity for area (the architecture expects rounding to
   the nearest 1,000 m² — verify it). Units used. How counts are expressed.
6. **Distractor spacing (MCQ)** — measure the numeric gaps between correct option and distractors,
   separately for area and count. Is spacing multiplicative, additive, or rank-based? This
   determines M4's distance function.
7. **Near-miss structure (binary)** — for quantitative binary questions, measure the distribution
   of `|stated − true|` for YES vs NO answers. Where is the real decision boundary? Is it
   relative, absolute, or something else? This determines M3.
8. **Adjacency phrasing** — how "adjacent" is worded, and whether any released examples let us
   infer the dilation convention.
9. **Class distribution & answer priors** — per task type, the marginal answer distribution. This
   is the class-prior baseline used in Stage 8.
10. **Referring-expression qualifiers** — enumerate the actual qualifier vocabulary (largest,
    smallest, north-most, etc.) with frequencies.

**DELIVERABLE:** `docs/architecture/ANSWER_GRAMMAR.md` containing every finding above, with the
supporting query/statistic for each claim. Every statement must be backed by a number computed from
the real data. Where the data is inconclusive, write `INCONCLUSIVE` and say what additional
evidence would settle it.

Also produce `reports/experiments/benchmark_forensics.md` with the analysis code paths and outputs.

**CRITICAL:** do not touch the quarantined benchmark evaluation split. Use train/val annotations
only. State in the deliverable which split each statistic came from.

**HALT IF:** the answer grammar contradicts a core architectural assumption (e.g. the questions
turn out to reference the 19-class vocabulary, or area is not rounded as expected). Emit a Gate
Report — this would change M2's design and must not be resolved unilaterally.

Then stop.

◀ END

---

# STAGE 4 — Taxonomy Layer (44 → hierarchy → coarse-7 → synonyms)

▶ START

Read `CLAUDE.md` §1 and `docs/architecture/ANSWER_GRAMMAR.md`.

Build the taxonomy layer. This is the fix for the architecture's single most important correction:
**44 CORINE L3 classes are the segmentation target; 19 classes are not.**

**BUILD:**

1. **`configs/taxonomy.yaml`** — the complete CORINE nomenclature:
   - all 44 Level-3 classes with official codes, names, and integer training indices
   - Level-3 → Level-2 → Level-1 parent relationships
   - Level-3 → 19-class multi-label mapping (auxiliary head only)
   - Level-3 → coarse-7 mapping: built-up, cropland, tree cover, grassland/shrub, water,
     bare/sparse, wetland
   - ESA WorldCover 11-class → coarse-7 mapping (for the India comparison in S23)
   - SECOND 6-class taxonomy (for M6)
   - the `unclassified`/no-data index, explicitly marked as ignored in loss and metrics
2. **`src/taxonomy/`** — a typed API:
   - `to_level(class_map, level)` — aggregate an L3 map to L1/L2/19/coarse-7
   - `mask_for(class_map, class_query, level)` — produce the binary mask for a requested class at
     a requested level
   - `siblings(class_id)`, `l1_branch(class_id)` — for the hierarchy-aware loss and the sibling
     confusion prior
   - `hierarchy_penalty_matrix()` — 44×44 matrix, 1.5× for cross-Level-1 confusion, 1.0× for
     sibling confusion, as specified in the architecture
3. **Synonym table** — `configs/synonyms.yaml` mapping natural-language surface forms
   (urban / urban fabric / built-up / artificial surface / woodland / forest / water body / ...)
   to the correct class at the correct level. Derive the vocabulary from the real question text
   found in Stage 3, not from imagination. Record any surface form you could not resolve.
4. **Aggregation-before-geometry guarantee** — document and enforce that hierarchy aggregation
   happens *before* connected-component analysis, so one conceptual region is never counted as
   several because its L3 subclasses differ.

**TESTS:**
- all 44 L3 classes present, uniquely indexed, contiguous indices
- every L3 class maps to exactly one L2, one L1, and one coarse-7 class
- round-trip: aggregating a synthetic L3 map to coarse-7 gives the expected pixel counts
- adjacent-subclass case: a synthetic map with continuous + discontinuous urban fabric side by side
  aggregates to **one** artificial-surfaces component, not two
- penalty matrix is symmetric, diagonal is zero, cross-L1 entries are 1.5×
- every synonym resolves to a valid class; unresolved surface forms are reported, not silently dropped

**HALT IF:** Stage 3 showed questions reference a level your mapping cannot express.

Show real test output. Then stop.

◀ END

---

# STAGE 5 — V1 Input Validation + Sensor Preprocessing

▶ START

Read `CLAUDE.md` §1. Implement Stage 1 and Stage 2 of the architecture pipeline.

**BUILD — V1 validator (`src/data/validation.py`):**

Accepts 1 or 2 GeoTIFFs + a text query. Uses **rasterio only** — never PIL, OpenCV, or generic
`imread`. Checks: band count, dtype, CRS, geotransform, image shape, NoData values, modality
(S1/S2), co-registration of the two images when two are supplied, and metadata strings.

Produces a Pydantic `InputManifest` (bands present, GSD, CRS, shape, modality, co-registration
status, metadata) **or** raises a typed `InputValidationError` naming the exact failed check.
Never coerce a broken input into a "best effort" manifest.

**BUILD — preprocessing (`src/preprocessing/`):**

- **Sentinel-1:** VV, VH → linear power → dB → z-score normalization using **training-set
  statistics only**. Handle zeros/negatives before the log safely and explicitly.
- **Sentinel-2:** B02, B03, B04, B05, B06, B07, B08, B8A, B11, B12. Keep 10 m bands at 10 m;
  bilinearly resample 20 m bands to 10 m; discard 60 m bands. Normalize with training statistics.
- **Output tensor:** 12 × H × W (2 SAR + 10 optical).
- **Band-presence mask:** a length-10 vector marking which optical bands are real vs dropped, so
  the model can distinguish "genuinely dark surface" from "band unavailable". Wire it through as a
  first-class model input, not an afterthought.
- **Optional spectral indices:** NDVI, NDWI, NDBI implemented behind config flags, defaulting to
  **off**. The architecture says these are ablation candidates, valuable mainly under band dropout
  — do not enable them by default.
- **Normalization statistics script** — computes per-band mean/std over the **training split only**,
  writes to `configs/norm_stats.yaml` with the split hash and sample count recorded.

**TESTS:**
- valid GeoTIFF → correct manifest; wrong band count / missing CRS / mismatched shapes / non-co-registered
  pair each raise the correct typed error
- SAR dB conversion is numerically correct on known inputs; zero/negative power handled without NaN
- 20 m bands resample to the correct shape; 60 m bands are absent from output
- output tensor is exactly 12 channels in the documented band order (assert the order explicitly)
- band-presence mask correctly reflects a synthetic dropout
- **leakage test:** normalization statistics computed from the training split alone; assert that
  changing validation data does not change the stats
- edge cases: single-band file, all-NoData tile, extreme values, uint16 vs float32 input

Show real test output. Then stop.

◀ END

---

# STAGE 6 — Geographic Splitting & Leakage Detection

▶ START

Read `CLAUDE.md` §1 and §7. The architecture explicitly **rejects random train/validation splits**
because neighbouring satellite patches are spatially correlated.

**BUILD:**

1. **Geographic block cross-validation, k = 5** — blocks defined by country or by 1° grid cell
   (implement both; make the choice a config option and report which the data supports better).
   Patches from the same block never appear in two folds.
2. **Held-out geographic test split** for final evaluation — geographically disjoint from all
   training folds.
3. **Split manifest** — deterministic, seeded, serialized to `data/processed/splits/*.json` with
   the seed, block definition, and per-fold class distribution recorded. Splits are an artifact,
   not something recomputed on the fly.
4. **Leakage test suite** (`tests/integration/test_leakage.py`) — automated checks for:
   - geographic leakage: minimum inter-fold distance; assert no block spans folds
   - duplicate leakage: exact and near-duplicate patch detection (hash + perceptual/statistical)
   - temporal leakage where acquisition dates exist
   - preprocessing leakage: assert no fitted statistic saw validation or test data
   - contamination: assert the quarantined benchmark split intersects nothing
5. **Split quality report** → `reports/evaluation/split_report.md`: per-fold sample counts,
   per-fold CLC L3 class distribution, rare-class coverage per fold, geographic coverage map.

**MEASURE AND REPORT:**
- per-fold class distribution divergence (rare classes must appear in every fold — if a class is
  absent from a fold, say so loudly)
- how much a **random** split would have inflated apparent similarity between train and val
  (compute a same-block-pair rate for random vs geographic). This number is judge-facing evidence
  that the split discipline matters — save it.

**HALT IF:** rare CLC classes cannot be covered across all folds under geographic blocking, or the
data lacks the geographic metadata needed to block properly.

Show real numbers. Then stop.

◀ END

---

# STAGE 7 — M2 Symbolic Geometry Engine + Convention Fitting

▶ START

Read `CLAUDE.md` §1–2 and `docs/architecture/ANSWER_GRAMMAR.md`.

Build M2 — the deterministic heart of the architecture. **M2 contains no neural network.**
`scipy.ndimage` + `skimage.measure` only.

**PART A — Engine (`src/geometry/`):**

Pipeline order is fixed by the architecture:

```
class map -> hierarchy aggregation -> binary mask -> morphological cleanup
          -> connected components -> MMU filter -> region properties -> task computation
```

Implement each operation:

- **Hierarchy aggregation** (via the Stage 4 taxonomy API) — always before components
- **Binary mask** for the requested class at the requested level
- **Morphological cleanup** — `binary_opening`, `binary_fill_holes`; radii come from config, not
  from hardcoded literals
- **Connected components** — `scipy.ndimage.label`, connectivity from config (4 or 8)
- **MMU filter** — discard components below the configured pixel threshold
- **Region properties** — `regionprops`: area, bbox, centroid, fill ratio

Task computations:

- **Presence:** `len(components) > 0`
- **Count:** number of surviving components
- **Area:** `pixel_count × GSD²`, rounded per the convention verified in Stage 3
- **Adjacency:** `binary_dilation(A, k) ∩ B` non-empty, k from config
- **Relative position:** centroid comparison → 8-way compass (N, NE, E, SE, S, SW, W, NW)
- **Referring expression:** candidate filter `1% ≤ area ≤ 50%` of image and `bbox fill ≥ 40%`,
  then select by the query qualifier (largest / smallest / north-most / ...)
- **Referring point:** which component contains (x, y) → return its bbox
- **Caption attributes:** class present, region count, area, region size, adjacency, and tier
  (`>25%` primary, `5–25%` secondary, `<5%` marginal)

All outputs are **typed structures** (Pydantic/dataclass), never strings. Every result carries the
parameters that produced it, so the answer is auditable.

**PART B — Convention fitting (`scripts/fit_geometry_conventions.py`):**

The architecture requires these to be **fitted against ground-truth maps and released answers**, not
guessed:

1. **Connectivity 4 vs 8** — run both against GT maps + released count answers; report accuracy for
   each; pick the winner and record the margin
2. **MMU threshold** — sweep the threshold; plot accuracy vs threshold; select and record
3. **Dilation radius k for adjacency** — sweep; report accuracy per k
4. **Area rounding granularity** — confirm against released area answers
5. **Opening/fill radii** — sweep on GT maps

Fit on the **training annotation split only**. Write results to
`reports/experiments/geometry_conventions.md` with the full sweep tables, and write the chosen
values into `configs/m2.yaml`.

**TESTS:**
- known synthetic masks → exact expected counts under both connectivities (include the diagonal
  checkerboard case)
- area arithmetic exact for a known pixel count and GSD
- adjacency: touching, one-pixel-gap, and far-apart pairs behave correctly across k
- compass directions correct for 8 synthetic placements
- MMU removes a 3-pixel blob and keeps a large region
- aggregation-before-components: adjacent L3 siblings yield one component
- determinism: same input → byte-identical output across runs
- edge cases: empty mask, full-image mask, single pixel, checkerboard, ring shape

**CONSTRAINT:** no learned component anywhere in M2. If you find yourself wanting one, stop and
report it as a Gate Report.

Show the fitting tables and real test output. Then stop.

◀ END

---

# STAGE 8 — ORACLE EXPERIMENT + BLIND BASELINES  ⛔ **GATE 1**

▶ START

Read `CLAUDE.md` §11. **This is GATE 1 — the most important measurement in the project so far.**

The architecture refuses to guess accuracy. It defines `TARGET(t) = ORACLE(t) × TRANSFER(t)`.
This stage measures ORACLE.

**BUILD — evaluation harness (`src/evaluation/`):**

A reusable harness that scores any answer producer against any annotation split, per task type:
presence, count, area, adjacency, relative position, referring expression, referring point,
metadata MCQ, caption. Metrics: accuracy per task type, plus BLEU-4 / ROUGE / METEOR / CIDEr for
captions. Every run emits a structured result artifact with split sizes, seed, config hash, and
per-task breakdown.

**RUN — Experiment O1: Oracle symbolic accuracy**

Feed **ground-truth CORINE reference maps** (not predictions) into M2, produce answers, score them.
This is the ceiling of the symbolic method. Report per task type.

**RUN — Experiment O2: Caption oracle**

Ground-truth map → M2 attributes → template caption → BLEU/ROUGE/METEOR/CIDEr against reference
captions. This decides the M8 gate later:
`BLEU ≥ 35` → skip M8 · `10 ≤ BLEU < 35` → build M8 · `BLEU < 10` → use M7 for captioning instead.

**RUN — Baselines (mandatory, per `CLAUDE.md`):**
- **Blind:** question text only, no image (train a simple text-only classifier on the training annotations)
- **Majority:** most common answer per task type
- **Class prior:** marginal land-cover distribution

**DELIVERABLE:** `reports/evaluation/GATE1_oracle.md` containing:
- oracle accuracy per task type, with counts and confidence intervals
- oracle caption metrics
- blind / majority / class-prior baselines per task type
- the gap between oracle and the best blind baseline — **this is the headline number**
- for every task where oracle is low: a diagnosis of *why*, categorised as hierarchy-aggregation
  error, connectivity error, MMU error, rounding/grammar error, or parser error

**⛔ MANDATORY STOP — emit a Gate Report and wait for my decision. Interpretation guide:**

- **Oracle high (say ≳90%) and far above blind** → the architecture's core bet is validated; proceed.
- **Oracle moderate** → the symbolic path works but the answer grammar or fitted conventions are
  imperfect. Report which task types are dragging it down before I decide.
- **Oracle low** → improving M1 will NOT fix this. The geometry or answer-grammar assumptions are
  wrong. Do not proceed to training. Report and stop.
- **Blind baseline close to oracle** → the benchmark may not be testing vision for that task type.
  Say so explicitly; this is important honesty for judges.

Do not proceed to Stage 9 until I respond.

◀ END

---

# STAGE 9 — Q1 Query Parser + M10 Fallback Classifier

▶ START

Read `CLAUDE.md` and `docs/architecture/ANSWER_GRAMMAR.md`. Implement architecture Stage 3.

The architecture is explicit: **rule-based parser first, no LLM.** The benchmark has a closed
vocabulary, so closed template rules are the correct tool.

**BUILD — Q1 rule-based parser (`src/routing/parser.py`):**

Converts a question string into a typed `QuerySpec`:

```
intent      : PRESENCE | COUNT | AREA | ADJACENCY | RELATIVE_POSITION |
              REFERRING_EXPR | REFERRING_POINT | METADATA_MCQ | CAPTION | CHANGE
class_a     : resolved class id + CLC level
class_b     : optional second class (adjacency, relative position)
qualifier   : north_of / largest / smallest / ... (from the Stage 3 vocabulary)
clc_level   : which hierarchy level the question targets
stated_value: for quantitative binary questions ("approximately 45,000 m²")
options     : for MCQ
answer_format: from ANSWER_GRAMMAR.md
```

Rules are built from the **real question templates observed in Stage 3**, not invented. Use the
Stage 4 synonym table for class resolution. On failure, the parser returns an explicit
`ParseFailure` with the reason — it never guesses.

**BUILD — M10 fallback (`src/routing/m10_classifier.py`):**

TF-IDF → **Linear SVM** → 8-way task classification. CPU only. Trained on the training annotation
split. Fires only when the rule parser fails. Persist the fitted vectorizer + model with the
training-split hash.

Why SVM and not an LLM: this is closed-set classification, it is cheap, and it is auditable.
Do not substitute a language model here.

**MEASURE AND REPORT:**
- rule-parser coverage: % of training questions parsed successfully, per task type
- rule-parser precision: on parsed questions, % where extracted intent/class match the annotation
- M10 accuracy on the questions the rules failed on: accuracy, macro-F1, confusion matrix
- combined coverage
- a list of the **unparsed residue** with example questions — this is the honest limitation list

**TESTS:** golden set of hand-labelled questions per intent; synonym resolution; stated-value
extraction with units and separators ("45,000 m²", "45000 sq m"); MCQ option extraction; malformed
input; empty string; very long input; injection-style strings (must be treated as text, never
executed).

**HALT IF:** rule coverage is low enough that M10 becomes the primary path rather than a fallback —
that inverts the architecture's intent and needs a decision.

Show real coverage numbers. Then stop.

◀ END

---

# STAGE 10 — R1 Deterministic Router + Typed Contracts + Scene Cache

▶ START

Read `CLAUDE.md` §1–2. Implement architecture Stage 4 and the scene cache.

**BUILD — R1 router (`src/routing/router.py`):**

Maps `(intent × input configuration) → frozen tool plan`. The plans from the architecture:

- `AREA` → M1 → M2 → (M3 if the question is a yes/no quantity comparison) → M9 → assembler
- `COUNT` / `PRESENCE` / `ADJACENCY` / `RELATIVE_POSITION` → M1 → M2 → (M3) → M9 → assembler
- `REFERRING_EXPR` / `REFERRING_POINT` → M1 → M2 → M9 → assembler
- `METADATA_MCQ` → M5 → M4 → M9 → assembler
- `GEOMETRIC_MCQ` → M1 → M2 → M4 → M9 → assembler
- `CAPTION` → M1 → M2 → caption attributes → M8 or M7 → assembler
- `CHANGE` (two images) → M6 → transition matrix → M2 → M3/M4 → M9 → assembler

**Hard constraints (architectural, non-negotiable):**
- No LLM decides which tool runs
- No `eval()`, no `exec()`, no dynamic import, no plugin loading
- The tool registry is **frozen at import time**
- Every tool call's parameters are validated with Pydantic before execution
- The same intent always produces the same plan — assert this in a test

**BUILD — typed inter-component contracts (`src/contracts.py`):**

Pydantic models for every boundary: `InputManifest`, `QuerySpec`, `ToolPlan`, `SegmentationResult`,
`GeometryResult`, `MetadataResult`, `ChangeResult`, `DecisionResult`, `ConfidenceResult`,
`FinalAnswer`. Components exchange **only** these. Natural language between components is forbidden.

**BUILD — scene cache (`src/inference/cache.py`):**

Key = `hash(scene bytes) + model version + preprocessing config hash`. Caches the M1 land-cover map
so three questions about one image run segmentation once. A different checkpoint must produce a
different key — write a test that proves a checkpoint change invalidates the cache.

**BUILD — execution trace:**

Every run records: task, tools invoked, parameters, timings, model names, weight hashes. This trace
is a deliverable, not a debug log.

**TESTS:**
- every intent produces the documented plan; determinism across 100 runs
- an unknown intent raises `RoutingError` rather than falling through to a default
- contract violation (wrong type at a boundary) raises `ContractViolationError`
- cache hit/miss behaviour; checkpoint change invalidates; corrupted cache entry is rejected not used
- a malicious query string never reaches any dynamic execution path (assert no `eval`/`exec` in `src/`)
- trace is complete and serializable for every task type

Show real test output. Then stop.

◀ END

---

# STAGE 11 — M1 Implementation + Smoke Test + Training Runbook

▶ START

Read `CLAUDE.md` §1 and §4. Build M1 — the most important learned model in the architecture.
**In this stage you build and smoke-test it. You do not run full training.**

**BUILD — model (`src/models/m1/`):**

Dual-encoder U-Net, exactly as specified:

- **Encoder A:** ConvNeXt-V2-Tiny over S1 (2 channels)
- **Encoder B:** ConvNeXt-V2-Tiny over S2 (10 channels)
- **Fusion:** concatenate → 1×1 convolution → Squeeze-and-Excitation gate
- **Decoder:** U-Net decoder with skip connections
- **Heads:** primary 44-class L3 head; auxiliary 19-class head; auxiliary coarse-7 head
- **Band-presence mask** wired in as an input signal
- **Output:** 44 × 120 × 120 logits
- **Parameter count:** report it — the architecture expects roughly 30–45M. If you are far outside
  that range, stop and tell me.
- Also implement **ResNet-34 encoders** as the configured alternative (architecture's stated fallback)

**BUILD — loss (`src/models/m1/loss.py`):**

`L = L_CE + 0.5·L_Lovasz + 0.3·L_hier + 0.2·L_scale`

- `L_CE`: cross-entropy, unclassified pixels ignored, class weights = inverse-square-root frequency
  capped at 5×
- `L_Lovasz`: Lovász-Softmax (IoU surrogate)
- `L_hier`: hierarchy-aware penalty using the Stage 4 44×44 matrix (1.5× cross-Level-1, 1.0× sibling)
- `L_scale`: scale consistency — resample 0.5×–4×, predict, resample back, KL divergence against
  the original prediction

Each term individually unit-tested with known inputs before they are combined.

**BUILD — data pipeline (`src/models/m1/dataset.py`):**

Uses the Stage 5 preprocessing and Stage 6 geographic splits. Augmentations: horizontal flip,
vertical flip, rotations, band dropout (keep-B02/B03/B04/B08 case included), modality dropout
(drop S1 or S2 entirely), scale jitter 0.5×–4×, SAR speckle, radiometric jitter.
**NO Mixup. NO CutMix** — they create artificial boundaries and corrupt connected-component logic.

Class balancing: inverse-sqrt weighting (capped 5×), Lovász, rare-class oversampling **2–3× only**
(not 10×), and per-class IoU reporting.

**BUILD — training script + config** with checkpointing, resume, mixed precision, seed control,
per-class IoU logging, and early stopping on the geographic validation fold.

**RUN NOW — smoke tests (you must actually execute these):**
1. Forward pass with random input → correct output shapes for all three heads
2. Parameter count reported
3. **Overfit 10 batches to near-zero loss** — if it cannot overfit a tiny batch, the model or loss
   is broken and no amount of training will help. Report the loss curve.
4. Each loss term computed on known synthetic inputs matches hand-calculated expectations
5. Augmentations preserve label alignment (assert mask transforms match image transforms)
6. One full epoch on a tiny subset completes without crashing; report time per step and VRAM

**THEN EMIT A TRAINING RUNBOOK** per `CLAUDE.md` §4: exact commands, hardware needed, estimated
wall-clock for the development subset and for the full 229,114-patch split, VRAM and disk needs,
checkpoint paths, and exactly what metrics I should paste back to you.

**Do not claim any training result. Stop after the runbook.**

◀ END

---

# STAGE 12 — M1 Training & Segmentation Evaluation (human-in-the-loop)

▶ START

Read `CLAUDE.md` §4. I have run the training from your Stage 11 runbook. Here are the real results:

```
<PASTE: final metrics, per-class IoU table, training/validation curves, wall-clock, any tracebacks>
```

**ANALYSE — do not immediately propose model changes.**

1. **Verify training health:** loss curves, train vs validation gap, over/underfitting signs,
   whether it converged or was cut short, learning-rate behaviour.
2. **Report segmentation metrics properly:** overall mIoU, **per-class IoU for all 44 classes**,
   pixel accuracy, and mIoU at each hierarchy level (44 / 19 / coarse-7). Overall mIoU hides rare
   class failure — the architecture insists on per-class reporting.
3. **Rank the failure classes** and diagnose each: is it rare-class starvation, spectral confusion
   with a sibling, cross-Level-1 confusion, boundary imprecision, or label noise in CORINE itself?
4. **Confusion analysis:** which class pairs dominate the error mass? Are they siblings (expected,
   tolerable) or cross-Level-1 (serious, because the hierarchy loss was supposed to suppress them)?
5. **Geographic generalisation:** performance per fold. High variance across geographic folds is a
   direct warning about the India transfer in Stage 23.
6. **Leakage re-check:** confirm the reported number came from a geographically blocked fold.

**DELIVERABLE:** `reports/evaluation/m1_segmentation.md` with all of the above, plus an entry in
`reports/experiments/EXPERIMENT_LOG.md`.

**If results are weaker than expected**, do NOT jump to a different architecture. Walk the debugging
hierarchy from `CLAUDE.md` in order: dataset → labels → preprocessing → leakage → split → features →
class imbalance → model assumptions → hyperparameters → alternative model. Report where in that
chain the evidence points, then **emit a Gate Report and stop.**

Candidate next moves for me to choose between (do not act unilaterally):
A) train longer / adjust schedule  B) fix class balancing  C) ImageNet-init ablation (architecture
allows this as an ablation)  D) SegFormer candidate as the architecture's alternative
E) accept current M1 and measure transfer factor first — the architecture argues this is often the
right call, because mIoU is not the metric that matters here.

Then stop.

◀ END

---

# STAGE 13 — TRANSFER FACTOR MEASUREMENT  ⛔ **GATE 2**

▶ START

Read `CLAUDE.md` §11. **This is GATE 2.**

Stage 8 measured ORACLE (perfect maps → M2 → answers). Now measure what survives real segmentation.

**RUN — Experiment T1:**

```
M1 predicted map -> M2 -> answers -> score with the Stage 8 harness
```

Same annotation split, same harness, same metrics as the oracle run. Then compute, per task type:

```
TRANSFER(t) = PREDICTED_ACCURACY(t) / ORACLE_ACCURACY(t)
```

**DELIVERABLE:** `reports/evaluation/GATE2_transfer.md` containing:
- side-by-side table: task type | oracle | predicted | transfer factor | blind baseline
- **count-error decomposition** — the architecture requires these be analysed separately:
  - **over-counting:** one real region fragmented into several predicted components (fixable via opening)
  - **under-counting:** two real regions bridged into one predicted component (fixable by removing false bridges)
  - report the frequency of each
- **error attribution** — for a sample of wrong answers, classify the root cause as: segmentation
  error / hierarchy-aggregation error / connectivity convention / MMU threshold / decision boundary /
  parse failure. Give counts per category. This table tells us where the next improvement should come from.
- correlation between per-class IoU and per-task answer accuracy — does better segmentation of a
  class actually translate into better answers about it?

**Refit note:** the architecture says symbolic parameters (MMU, dilation, opening) were fitted on
ground-truth maps; they may need refitting on **predicted** maps, which behave differently. Report
whether refitting on predicted maps improves accuracy, and by how much — but present it as a
measured option, not an automatic change.

**⛔ MANDATORY STOP — Gate Report. Interpretation guide:**

- **High oracle + high transfer** → architecture is working. Proceed.
- **High oracle + low transfer** → the bottleneck is M1. Improving segmentation is the correct
  investment. Report which classes cost the most answer accuracy.
- **Low oracle** (already known from Gate 1) → M1 improvements will not rescue it.
- **Predicted accuracy ≤ blind baseline for a task** → the vision path adds nothing for that task.
  Say so explicitly and honestly.

Do not proceed until I decide.

◀ END

---

# STAGE 14 — M3 Binary Decision Head + M4 MCQ Option Scorer

▶ START

Read `CLAUDE.md` §1 and `docs/architecture/ANSWER_GRAMMAR.md` (near-miss and distractor-spacing
findings). Implement architecture Stage 7's decision layer.

**BUILD — M3 (`src/models/m3/`):**

Binary YES/NO for quantitative questions. The architecture's key insight: the benchmark's "NO"
answers are deliberately **near misses**, so a fixed tolerance like ±10% is wrong. The decision
boundary must be learned.

Model: **LightGBM (~200 trees, depth 4)**, with **L2 logistic regression** implemented as the
interpretable alternative. Compare both — if logistic regression is within noise, prefer it for
auditability (`CLAUDE.md` §11 model-selection criteria).

Features (from the architecture): computed value, stated value, absolute difference, log ratio,
rank difference, question subtype, class ID, class pixel share, mean segmentation margin, TTA count
standard deviation, components near MMU, sibling confusion prior.

**CRITICAL — train on predicted maps, not ground-truth geometry:**
```
M1 predicted map -> M2 computed value -> M3 features
```
This lets M3 learn and compensate for M1's *systematic* biases (e.g. consistent over-segmentation).
Training on perfect geometry would throw that away. Document this explicitly.

**BUILD — M4 (`src/models/m4/`):**

MCQ option scorer. `score(option_k) = −distance(computed, option_k)` → softmax over four options.

Distance function is **fitted, not assumed**, using the Stage 3 distractor-spacing findings:
- **area** → log-scale distance
- **count** → rank-scale distance
- temperature fitted on the training split

Two branches: **geometric MCQ** (presence, area, count, adjacency, relative position → uses M2) and
**metadata MCQ** (country, season, climate → uses M5, built in Stage 15).

**MEASURE:**
- M3: accuracy, precision/recall, ROC-AUC, PR-AUC, calibration curve, Brier score — vs. a fixed-tolerance
  baseline (±5%, ±10%, exact match). Show that learning the boundary beats fixed tolerance, or report
  honestly that it does not.
- M4: accuracy vs. naive absolute-difference baseline, per subtype.
- Both: compare against the blind and majority baselines from Stage 8.

**TESTS:** feature extraction determinism; no leakage of the validation split into feature fitting;
degenerate cases (computed = 0, stated = 0, all options equidistant, missing stated value);
serialization round-trip.

**HALT IF:** M3 fails to beat fixed tolerance, or M4 fails to beat absolute difference — that means
the Stage 3 grammar findings were wrong and need revisiting.

Show real numbers. Then stop.

◀ END

---

# STAGE 15 — M5 Scene Metadata Classifier (GATED)

▶ START

Read `CLAUDE.md` and `docs/architecture/ANSWER_GRAMMAR.md`.

**FIRST — CHECK THE GATE BEFORE BUILDING ANYTHING.**

The architecture states: *if the benchmark's input metadata already provides country, date, and
geolocation, M5 may be unnecessary* — because geolocation → country lookup is exact, and date →
season is exact.

State the Stage 3 finding explicitly:
- Is country available in the benchmark input? YES / NO
- Is acquisition date available? YES / NO
- Is geolocation available? YES / NO

**If all three are available:** do NOT train M5. Instead implement a deterministic metadata resolver
(geolocation → country via a boundary lookup; date → season; geolocation → Köppen climate zone via a
climate raster), wire it into the router in place of M5, document the decision in
`docs/architecture/DECISIONS.md`, and report the compute saved. Then stop.

**If metadata is absent or partial:** build M5 as specified:

- Model: **ConvNeXt-Tiny**, 12-channel input, **3 classification heads**: country (10 classes),
  season (4 classes), Köppen climate (k classes)
- Training: **transfer learning** from ImageNet (unlike M1 — this is a scene-classification task
  where ImageNet features genuinely help)
- Labels: reBEN metadata (country, acquisition date, geolocation); Köppen zone derived from
  coordinates via a climate raster
- MCQ inference: full class probabilities → **restrict to the four offered options** → argmax.
  This is much easier than open-set classification and must be implemented that way.
- Splits: the same geographic blocking from Stage 6 (country classification with random splits would
  be catastrophically leaky — a test must assert this)

**MEASURE:** per-head accuracy and macro-F1; confusion matrices; MCQ-restricted accuracy;
comparison against the majority baseline per attribute.

**Emit a training runbook** if full training is needed; smoke-test first (overfit 10 batches).

**HALT IF:** country accuracy is near chance — geographic leakage or an impossible task; either way
I need to know before it goes in front of judges.

Then stop.

◀ END

---

# STAGE 16 — A1 FALSIFICATION EXPERIMENT  ⛔ **GATE 3**

▶ START

Read `CLAUDE.md` §11. **This is GATE 3 — the falsification test.** Its purpose is to give the
project a chance to *fail honestly* before more compute is spent.

Run all six systems on the **same** annotation split with the **same** harness:

| System | What it does |
|---|---|
| **Blind** | question text only, no image |
| **Majority** | most common answer per task type |
| **Class prior** | marginal land-cover distribution |
| **VLM-only** | InternVL3-1B zero-shot answers everything |
| **Symbolic** | M1 → M2 → M3/M4 (the architecture's path) |
| **Oracle** | GT map → M2 → M3/M4 (the ceiling) |

For the VLM-only arm, use InternVL3-1B **zero-shot** — no fine-tuning yet. That is the honest
comparison point (the architecture warns against pretending to reproduce the published 34.04 BLEU
fine-tuned setup, which used 4×H200 and per-task adapters).

**DELIVERABLE:** `reports/evaluation/GATE3_falsification.md`:
- full matrix: system × task type, with counts
- **bootstrap confidence intervals resampled at the image-pair level, not the annotation level**
  (annotations within a pair are correlated — resampling at annotation level would fake precision)
- **McNemar's test** for the paired comparisons that matter: symbolic vs VLM, symbolic vs blind,
  symbolic vs oracle
- explicit significance statement: per the architecture, do **not** treat differences below ~3 points
  (binary) or ~4 points (MCQ) as meaningful without stronger evidence
- the adjacency comparison called out separately — this is the architecture's flagship demonstration
  (a reported ~2T-parameter model reached only 55.86% on binary adjacency, while adjacency is exactly
  computable via `binary_dilation(A) ∩ B` once the map is right). Report our adjacency number against
  that reference honestly, including whether our own segmentation quality limits it.

**⛔ MANDATORY STOP — Gate Report. This decides the rest of the project:**

- **Symbolic clearly beats VLM-only and blind on geometric tasks** → the architecture's thesis holds.
  Proceed to build out the remaining components.
- **Symbolic ≈ VLM-only** → the symbolic advantage is not materialising. Report why (oracle ceiling?
  transfer loss? grammar mismatch?) and stop for a strategy decision.
- **Symbolic < blind on any task** → something is fundamentally wrong with that task's path. Name it.

The architecture's own instruction: *if symbolic isn't working, stop investing heavily in it and use
the VLM fallback.* Be willing to report that outcome. Do not proceed until I decide.

◀ END

---

# STAGE 17 — M6 Siamese Semantic Change Model + CDVQA

▶ START

Read `CLAUDE.md` §1. Implement the change branch.

**BUILD — M6 (`src/models/m6/`):**

- **Siamese U-Net with shared weights**: T1 → encoder, T2 → **the same encoder**. Shared weights are
  mandatory — independent encoders would learn date-specific representations rather than a common one.
- **Outputs:** semantic map T1, semantic map T2, change mask
- **Taxonomy:** SECOND, 6 classes (not CORINE) — because CDVQA's questions were generated from
  SECOND semantic change maps. We follow the benchmark's construction again.
- **Loss:** `semantic_T1 + semantic_T2 + change + 0.3·consistency`, where consistency enforces that
  differing T1/T2 classes → change ≈ 1 and matching classes → change ≈ 0
- **Training: ImageNet-pretrained encoder + full fine-tuning** — deliberately different from M1.
  M6 is data-poor (~2,968 public SECOND pairs, ~1,600 CDVQA training pairs) where M1 had 229k patches.
  Document this contrast; judges will ask why the two strategies differ.

**BUILD — transition matrix + CDVQA reasoning (`src/geometry/change.py`):**

`T[i][j]` = pixels moving from class i to class j. CDVQA questions become **arithmetic over this
matrix** — e.g. "what changed to buildings?" sums the Building column. Answers come from CDVQA's
closed set of **19 categories**. Route the arithmetic through M2 so the same auditable measurement
path applies. Reuse M3/M4 for binary/MCQ formatting.

**MEASURE:**
- M6: per-class IoU on SECOND semantic maps (T1 and T2 separately), change-mask F1/IoU
- CDVQA accuracy overall and per answer category, on the CDVQA validation split
- comparison against the majority baseline over the 19 categories
- **change-oracle**: run the transition-matrix reasoning on ground-truth SECOND maps to get the
  change-branch ceiling, exactly as Stage 8 did for the main branch. Report oracle and transfer.

**TESTS:** shared-weight assertion (encoder parameter objects are identical, not merely equal shapes);
transition matrix row/column sums equal expected pixel counts on synthetic pairs; consistency loss
behaves correctly on constructed agree/disagree cases; unregistered image pair is rejected by V1.

Smoke-test first (overfit 10 batches), then emit a **training runbook** and stop for me to run it.

**HALT IF:** the change-oracle is low — that means the transition-matrix formulation does not match
how CDVQA answers were generated, and training M6 harder will not fix it.

Then stop.

◀ END

---

# STAGE 18 — M9 Confidence Calibrator + TTA + Abstention

▶ START

Read `CLAUDE.md` §1 and the master prompt's §19 (Model Confidence). Implement architecture Stage 8.

The key distinction: **M9 estimates P(answer is correct), not raw model confidence.** A segmentation
that is 99% confident per pixel can still produce a wrong count by merging two regions. M9 therefore
operates at the **answer level**.

**BUILD — TTA (`src/inference/tta.py`):**

4 rotations × 2 flips = **8 transformations**. Apply, predict, invert the transformation, average
logits. Record the **per-transform answer variance** — stable answers across all 8 are trustworthy;
answers that swing (7, 8, 7, 6, 9, ...) are not. TTA serves two purposes: better predictions *and*
an uncertainty signal.

**BUILD — M9 (`src/models/m9/`):**

**L2 logistic regression + isotonic regression** → P(correct), plus a high/medium/low band.

Signals (from the architecture): mean class margin, TTA answer stability, component-count standard
deviation, area interval width, minimum component margin, band presence, sibling confusion prior.

Trained on `(features → was the final answer actually correct)` pairs from the training split, using
**predicted** maps.

**BUILD — abstention (`src/inference/abstention.py`), two modes:**

- **Operational mode:** if `P(correct) < threshold`, abstain and name the likely problem
  ("low segmentation margin on the forest/shrub boundary"). Useful and honest.
- **Benchmark mode:** abstention is scored as wrong, so never abstain. Fall back through the cascade:
  symbolic → M7 VLM → class prior → majority.

The fallback is a **cascade**, not an ensemble vote. Each task has one defined producer; M9 only
decides whether to trust it. Do not implement majority voting across M1/M5/M6/M7.

**MEASURE (this is what makes the confidence number defensible to judges):**
- **ECE** (expected calibration error) and a **reliability diagram**
- **Brier score**
- **risk–coverage curve** and AUC: accuracy on the answers we keep, as a function of coverage
- selective accuracy at 50% / 70% / 90% coverage
- comparison against a naive baseline (raw softmax margin as confidence) — show that M9 is better calibrated

**CONSTRAINT:** the UI must never display an uncalibrated percentage. If a confidence number is
shown, this stage's reliability diagram is the evidence behind it.

**TESTS:** TTA inversion is exact (transform → invert → identity); calibration on synthetic
over/under-confident data; abstention thresholds respected in both modes; benchmark mode never abstains.

Show the ECE and risk–coverage numbers. Then stop.

◀ END

---

# STAGE 19 — M7 InternVL3-1B + LoRA + Constrained Decoding

▶ START

Read `CLAUDE.md` §1–2. Implement M7 — deliberately **not** the central reasoning engine.

**M7's role:** free-form language, captioning, change narration, fallback, and compliance with the
RS-adaptation requirement.
**M7 is explicitly NOT responsible for:** counting, area, adjacency, relative position, or bounding
boxes. Those belong to the symbolic path. Enforce this in code — the router must not be able to send
a geometric intent to M7 except through the Stage 18 fallback cascade.

**BUILD (`src/models/m7/`):**

Architecture (following the published RS adaptation structure):
- S1 → BEN-pretrained ViT → projection
- S2 → BEN-pretrained ViT → projection
- RGB → InternViT-300M
- Text → tokenizer
- All → Qwen2.5-0.5B LLM with **LoRA (r=8, alpha=32, dropout=0.1)**
- Trainable: ~5.8M of ~1.1B. Report the actual trainable/total counts.

**Training curriculum (in this order, as specified):**
1. **Projection warm-up** — ~2,000 steps, LoRA frozen, train only the modality projections, because
   S1/S2 visual tokens are new inputs that must be mapped into the LLM's representation space
2. **LoRA + projections** trained on captioning (captions give dense language supervision)
3. Optional change-narration adapter
4. **Do NOT train VQA/MCQ/grounding adapters unless symbolic performance failed at Gate 3.** State
   the Gate 3 outcome and whether step 4 is authorised.

**Constrained decoding (`src/models/m7/decoding.py`) — mandatory reliability mechanism:**
- **Binary:** compare `logit("yes")` vs `logit("no")`. No free generation.
- **MCQ:** length-normalised log-likelihood of each option; pick the highest. No free generation.
- **Bounding box:** grammar-constrained decoding.
- **Caption:** free generation permitted.

**HONESTY REQUIREMENT:** the published 34.04 BLEU-4 result used 4×H200 GPUs, ~2 days, and per-task
fine-tuning. Do not claim to reproduce it. The fair comparison we report is
**InternVL3-1B zero-shot vs. our adapted InternVL3-1B**. Put that framing in the report.

**MEASURE:** zero-shot vs adapted, per task type; caption BLEU-4/ROUGE/METEOR/CIDEr; VRAM and
latency; the reference table from the architecture (best RS-specific 1.66/58.38/35.26/16.18; best
general CV 0.96/61.96/37.55/31.73; InternVL3-1B zero-shot 0.45/54.11/26.76/5.76) included **as
published context, clearly labelled as other people's numbers, not ours**.

Smoke-test, then emit a training runbook with realistic single-GPU wall-clock. Then stop.

◀ END

---

# STAGE 20 — M8 Caption Style Rewriter (GATED)

▶ START

Read `CLAUDE.md` and the Stage 8 caption-oracle result.

**FIRST — CHECK THE GATE. Do not build M8 before stating this.**

From the Stage 8 caption oracle (ground-truth map → template caption → BLEU):

- **BLEU ≥ 35** → templates are already good enough. **Skip M8.** Document and stop.
- **10 ≤ BLEU < 35** → **build M8.**
- **BLEU < 10** → templates are too far from the reference style. **Do not build M8** — use M7 for
  captioning. Document and stop.

State the measured BLEU and the resulting decision explicitly before writing any code.

**IF BUILDING M8 (`src/models/m8/`):**

Why it exists: the benchmark's reference captions were produced by
`template → Llama-4-Scout-17B paraphrasing → self-refinement`, so they do not look like our
templates. BLEU-4 rewards word-sequence overlap, so a factually perfect template can score badly.

- Model: **Flan-T5-base (250M)** or LoRA on **Qwen2.5-0.5B-Instruct**
- Input: our exact template string. Output: dataset-style caption.
- **M8 never sees the image.** The facts were already fixed by M2. This is a style transformation only.

**Factuality safeguard (mandatory):** after rewriting, re-extract the attributes from the generated
caption and compare against the source structured facts. **If the facts do not match, reject the
rewrite and fall back to the template.** This prevents "better BLEU" being bought with hallucination
("two water regions" → "several water regions" is a rejection, not an improvement).

**MEASURE:** BLEU-4/ROUGE/METEOR/CIDEr before vs after M8; **factuality rejection rate**; and a
factuality-preserved BLEU (scoring only accepted rewrites). Report all three — a BLEU gain with a
high rejection rate is not a real gain.

**HALT IF:** the rejection rate is high enough that M8 rarely fires, or BLEU does not improve.

Then stop.

◀ END

---

# STAGE 21 — Answer Assembler, Evidence, Execution Trace & PDF Report

▶ START

Read `CLAUDE.md` §2. Implement architecture Stage 9 — the output layer.

**THE STRONGEST RULE IN THE ARCHITECTURE:**
> A language model may phrase the answer, but it may **never** produce the numerical value.

If M2 computed 42,000 m², the assembler inserts `42,000 m²` into the template. The VLM cannot revise
it to 45,000. Enforce this in code and write a test that fails if any number in the final answer did
not originate from a typed geometry/metadata result.

**BUILD — assembler (`src/inference/assembler.py`):**

Takes typed results (`GeometryResult`, `DecisionResult`, `MetadataResult`, `ConfidenceResult`) and
formats them into the answer grammar from Stage 3. Numbers are substituted, never generated.

**BUILD — the four outputs:**

1. **Structured JSON** — value, unit, confidence, evidence references, task type, timestamp
2. **Evidence artifacts** — mask overlay, component contours, bounding boxes, area table, margin
   heatmap, GeoJSON, GeoTIFF (georeferenced, so it opens correctly in QGIS — verify this)
3. **Execution trace** — task, tools invoked, parameters, timings, model names, **weight hashes**
4. **PDF report** — question, input thumbnail, land-cover map, the arithmetic shown step by step
   (pixel count → area, or components → count), confidence with its calibration basis, execution
   trace, model hashes, dataset attribution

The PDF is the auditability showpiece: it must let a judge follow *why* the number is what it is,
not merely see the number.

**TESTS:**
- **number-provenance test:** every numeral in the final answer traces to a typed result field
- assembler output validates against the Stage 3 answer grammar for all task types
- GeoTIFF/GeoJSON evidence is correctly georeferenced (round-trip the CRS and transform)
- trace is complete, serializable, and reproducible; the same input yields the same trace
- PDF generates for every task type without crashing, including the abstention case
- **a fabricated-VLM-number injection test:** if a VLM string containing a different number reaches
  the assembler, the assembler must ignore it, not use it

Show a real generated PDF for the area example and the adjacency example. Then stop.

◀ END

---

# STAGE 22 — API / Backend Layer + Security

▶ START

Read `CLAUDE.md` §9 and the master prompt's §17 (security built in, not bolted on).

**BUILD — API (`src/api/`), FastAPI:**

Endpoints:
- `POST /query` — GeoTIFF(s) + question → full answer + evidence references
- `POST /query/change` — two GeoTIFFs + question
- `GET  /evidence/{run_id}` — evidence artifacts
- `GET  /report/{run_id}` — PDF report
- `GET  /health` and `GET  /ready` — liveness and model-loaded readiness
- `GET  /version` — model versions, weight hashes, git commit

Requirements: Pydantic request **and** response validation; async handling for long inference;
job/run IDs; structured logging with the run ID; OpenAPI docs; consistent typed error responses that
never leak stack traces or filesystem paths.

**BUILD — security (`src/security/`):**

- **File upload hardening:** size limits, extension **and magic-byte** verification, rasterio-based
  structural validation before anything else touches the file, decompression-bomb protection,
  quarantine directory, path-traversal prevention (never trust a client-supplied filename)
- **Input validation:** query length caps, character-set validation, and a test asserting that query
  text never reaches any dynamic execution path (grep `src/` for `eval`, `exec`, `pickle.loads`,
  `os.system`, `subprocess` with `shell=True` — assert none in request paths)
- **Rate limiting** per client, plus concurrent-job caps
- **Resource exhaustion protection:** max image dimensions, inference timeout, memory ceiling,
  GPU queue depth
- **Secrets:** environment variables only; assert no secret literal exists in the repo
- **Dependency audit:** `pip-audit` / `safety`; record findings in `docs/security/DEPENDENCY_AUDIT.md`
- **Logging hygiene:** no secrets, no full filesystem paths, no raw user file contents in logs
- **AuthN/AuthZ:** API key or token for non-public deployment, with the demo mode clearly documented

**TESTS (`tests/api/`, `tests/security/`):**
- valid requests for every task type
- invalid requests: missing file, wrong content type, oversized file, non-GeoTIFF renamed to `.tif`,
  corrupt GeoTIFF, malformed JSON, missing question, empty question
- path traversal attempts (`../../etc/passwd` as filename)
- injection strings in the question field
- rate limit triggers and returns the correct status
- timeout behaviour under a deliberately slow request
- concurrent requests do not corrupt the scene cache
- error responses never leak internals

**DELIVERABLE:** `docs/security/SECURITY_REVIEW.md` — every check performed, what was found, what
was fixed, and what remains as accepted risk. Honest residual risks are better than a clean-looking
document.

Show real test output. Then stop.

◀ END

---

# STAGE 23 — BHARAT-EO / Indian Domain Adaptation  ⛔ **GATE 4**

▶ START

Read `CLAUDE.md` §11. **This is GATE 4** and the project's strongest scientific argument for an
ISRO/SAC audience.

**Why this works in this architecture:** a VLM-only system would need Indian images *plus* Indian
text instructions *plus* Indian answers, and no Indian equivalent of BigEarthNet.txt exists. Our
hybrid concentrates the domain gap into **M1 alone**, where Indian pixel supervision *is* obtainable.
After M1 adapts, the geometry engine does not care whether the pixels came from Bavaria or Bengaluru —
the same mathematical operation applies.

**BUILD — BHARAT-EO corpus (`scripts/data/bharat/`):**

Same sensors as the European training data (**Sentinel-1 + Sentinel-2 at 10 m**) so the difference is
**geography alone**, not geography + sensor + resolution + preprocessing. This is what makes the
experiment scientifically clean — state it in the report.

Sampling must cover: agro-climatic zones, seasons, urban, peri-urban, rural, forest, coastal, arid —
with rare classes deliberately represented.

Weak labels:
- **ESA WorldCover 10 m** (11 classes) — weak supervision, **not** perfect ground truth
- **Dynamic World** — 10 m land cover **plus per-class probabilities**; use the probabilities to
  weight the training loss (a pixel where WorldCover says crop and Dynamic World says crop 0.94 is
  high-confidence; crop 0.38 / forest 0.42 is not)
- **Bhuvan (ISRO/NRSC)** — used for coarse validation, class-prior agreement, and independent
  cross-check. **Not** treated as equivalent to 10 m CORINE pixel labels.

**SPLIT — BHARAT-TRAIN vs BHARAT-VAL (geographic, never random):**
- BHARAT-TRAIN: Indian adaptation
- **BHARAT-VAL: final Indian evaluation only — never trained on, never tuned on, never used for
  early stopping.** Enforce with a loader guard and a test, same pattern as the benchmark quarantine.

**COARSE-7 MAPPING:** CORINE L3 (44) and WorldCover (11) have different taxonomies, so comparing them
directly is invalid. Map both to **coarse-7** (built-up, cropland, tree cover, grassland/shrub, water,
bare/sparse, wetland) and compare Europe vs India at that level only.

**ADAPTATION — four stages, in order:**
1. Re-estimate normalization statistics on Indian data. No gradient. Cheap. **Measure after this
   alone** — it may recover much of the gap for free.
2. Freeze the encoder; train decoder + head on Indian weak labels.
3. If still improving, unfreeze the last encoder stage at a very low learning rate.
4. Replay **20–30% European batches** to prevent catastrophic forgetting. **If European mIoU drops
   more than ~2 points, stop or back off.**

**ALSO RUN — sensor-gap simulation.** The hidden ISRO/SAC imagery may be Cartosat-2S or RISAT with
different resolution, bands, and SAR characteristics, and we do not have equivalent data.
**NEVER fabricate a Cartosat/RISAT accuracy number.** Instead measure robustness under: band dropout,
scale change 0.5×–4×, SAR speckle, and radiometric jitter, and report those as what they are —
simulated robustness, not measured performance on the real sensor.

**DELIVERABLE:** `reports/evaluation/GATE4_india.md`:
- **BHARAT-VAL coarse-7 mIoU** (the gate number)
- Europe coarse-7 mIoU side by side, and the gap
- per-adaptation-stage results (stage 1 / 2 / 3 / 4) so we can show what each step bought
- European mIoU after adaptation (catastrophic-forgetting check)
- downstream symbolic answer accuracy on Indian imagery, not just mIoU
- Bhuvan cross-check agreement
- sensor-robustness curves, clearly labelled as simulation

**⛔ MANDATORY STOP — Gate Report. Then stop.**

◀ END

---

# STAGE 24 — Final Evaluation, Ablations, Statistics & Error Analysis

▶ START

Read `CLAUDE.md` §7 and §11. This is the stage where the benchmark quarantine is finally lifted —
**once**.

**BEFORE TOUCHING THE BENCHMARK SPLIT:** confirm in writing that all tuning is complete, all
hyperparameters are frozen, all thresholds are fixed, and all model selection is done. Once the seal
is broken, no further tuning is legitimate. State this explicitly, then set `ALLOW_BENCHMARK_EVAL=1`.

**RUN — final evaluation on the quarantined split** (1,082 image pairs / 15,029 annotations:
6,927 binary, 5,550 MCQ, 970 captions, 1,582 referring), plus CDVQA test splits and the mandated
VRSBench/RSVQA evaluation-only runs.

**RUN — the six-system comparison** (blind / majority / VLM-only / symbolic-only / hybrid / oracle)
on the final split.

**RUN — ablations.** Each one removes exactly one thing and re-measures:
- dual encoder vs single fused encoder
- each M1 loss term removed (Lovász, hierarchy, scale consistency)
- spectral indices on vs off
- band-presence mask on vs off
- TTA on vs off
- hierarchy aggregation before vs after connected components
- M3 learned boundary vs fixed tolerance
- M4 fitted distance vs absolute difference
- M8 on vs off (if built)
- ImageNet init vs from-scratch for M1 (the architecture's designated ablation)

**RUN — statistics.** Bootstrap CIs resampled at the **image-pair level**; McNemar's tests for paired
system comparisons. Apply the architecture's significance discipline: differences below ~3 points
(binary) or ~4 points (MCQ) are not claimed as meaningful without stronger evidence. Say when a
result is inside the noise — that honesty is itself a strength in front of judges.

**RUN — full error analysis** → `reports/error_analysis/FINAL.md`, per the master prompt's format:
error category | affected samples | example cases | root-cause hypothesis | proposed solution |
expected impact | actual measured impact.

Categories: segmentation error, connectivity convention, MMU threshold, hierarchy aggregation,
decision-head boundary, parse failure, metadata error, change-model error, caption style.
Include the over-counting vs under-counting decomposition.

**RUN — perturbation tests:** noise, band dropout, scale change, speckle, radiometric shift,
co-registration error on image pairs. Report degradation curves.

**DELIVERABLE:** `reports/evaluation/FINAL_EVALUATION.md` covering data, models, baselines, final
metrics, ablations, statistics, error analysis, system latency/throughput/resources, security
results, test coverage, and reproducibility (environment, seeds, dataset and model versions).

**Report every number honestly, including the ones that disappoint.** Then stop.

◀ END

---

# STAGE 25 — Robustness, Adversarial & Integration Hardening

▶ START

Read `CLAUDE.md`. Final hardening pass before the demo build.

**RUN — end-to-end integration verification:**
- every task type end to end through the real API, with the real models
- two-image change path end to end
- scene cache correctness under repeated and concurrent questions about one image
- failure propagation: what a user sees when M1 fails, when M5 is absent, when a checkpoint is missing,
  when the cache is corrupt, when GPU memory is exhausted
- latency and memory profile per task type; report p50/p95 for each

**RUN — adversarial and edge-case suite:**
- all-NoData tile, single-class tile, uniform tile, extreme values, wrong CRS, missing geotransform
- 1-pixel image, very large image, mismatched pair sizes, non-co-registered pair
- out-of-distribution imagery (a non-satellite photo submitted as a GeoTIFF)
- questions about classes absent from the image
- questions about classes outside the taxonomy
- ambiguous, empty, and extremely long questions
- malformed MCQ (2 options, 6 options, duplicate options)
- unicode, RTL text, and injection-style strings in the question field

**THE STANDARD:** the system must **fail safely and legibly**, never silently produce a confident
wrong answer. For every edge case, record: input → behaviour → was it safe? If any case produces a
confident wrong answer rather than an error or abstention, that is a **critical bug** — fix it and
re-run.

**RUN — regression suite:** freeze golden outputs for a fixed set of inputs, so later changes cannot
silently alter answers. Include the trace and the numbers, not just the final string.

**DELIVERABLE:** `reports/evaluation/ROBUSTNESS.md` with the full case table and the fixes applied.

Then stop.

◀ END

---

# STAGE 26 — Demonstration System, Freeze & Judge Readiness Pack

▶ START

Read `CLAUDE.md`. Final stage. **Feature freeze applies: no new capabilities from here.**

**BUILD — demonstration frontend (minimal, honest):**
- upload one or two GeoTIFFs, type a question
- show: the answer, the land-cover map, the highlighted mask/components, the arithmetic that produced
  the number, the calibrated confidence, and the execution trace
- download the PDF report
- a **prepared demo set** of real inputs covering: area, count, adjacency, relative position,
  referring expression, metadata MCQ, caption, change, and **one deliberate abstention/failure case**

Show the failure case on purpose. A system that knows when it does not know is more convincing than
one that always answers.

**Constraint:** every number on screen comes from a real run. Nothing hardcoded, no cached
screenshots standing in for live inference. If something cannot run live, say so on the slide rather
than faking it.

**BUILD — judge readiness pack (`docs/JUDGE_PACK.md`)** — an evidence-backed answer to each question,
with a pointer to the report and the actual number:

1. Why this architecture? → benchmark ground truth was generated from pixel-level maps; we reproduce
   that construction (Gate 1 oracle is the evidence)
2. Why these models? → the bounded-responsibility cascade (M1…M10), with the pretraining-strategy
   contrast (M1 from scratch on 229k patches vs M6 transfer on ~1.6k pairs vs M7 LoRA on 1.1B params)
3. Why these datasets? → each dataset answers exactly one of the five questions in the architecture
4. Better than existing solutions? → the Gate 3 matrix, especially adjacency, framed as a **problem
   reformulation** rather than "our small model beats a 2T model"
5. How accurate, and how measured? → the final evaluation with CIs, not a single headline number
6. How was leakage prevented? → geographic blocking, quarantine guards, train-only statistic fitting,
   and the Stage 6 random-vs-geographic comparison
7. What happens on a wrong prediction? → M9 confidence, abstention, and the demonstrated failure case
8. Baselines? → blind, majority, class prior, VLM-only, oracle
9. Why not another model? → the ablation table
10. Security? → the Stage 22 security review, including residual risks
11. Real-world / India? → Gate 4, and the honest statement that Cartosat/RISAT numbers were **not**
    fabricated, only sensor robustness was simulated
12. Limitations? → M1 segmentation quality as the ceiling on everything downstream, and the Indian
    sensor gap

**BUILD — final artifacts:**
- `README.md` rewritten for a reviewer: what it does, how to run it, what the results are
- `docs/LIMITATIONS.md` — the honest list, including every `NOT YET VERIFIED` and
  `ASSUMPTION — REQUIRES VALIDATION` still outstanding
- reproducibility bundle: environment lock, seeds, config snapshots, dataset versions, model weight
  hashes, and a verified clean-environment reproduction of at least the inference path
- final `PROJECT_STATUS.md`

**FINAL AUDIT — run this and report the result:**
- grep the whole repository for fabricated or hardcoded results, placeholder metrics, and TODOs in
  production paths
- verify every number in every report traces to a real run artifact in `reports/runs/`
- verify the full test suite passes from a clean checkout
- verify `CLAUDE.md` §1 frozen facts still hold everywhere in the codebase

Report anything that fails the audit rather than quietly fixing it. Then stop.

◀ END

---

## APPENDIX A — Reusable Mid-Stage Prompts

Paste these whenever needed, between stages.

**Drift check:**
> Re-read `CLAUDE.md` §1. Audit the code written since the last stage against every frozen fact.
> Report contradictions as a list. Fix nothing until I approve.

**Metric challenge:**
> For the last reported metric: which split produced it, how many samples, what seed, which config
> hash, and which run artifact in `reports/runs/`? If you cannot point to a real artifact, mark it
> `NOT YET VERIFIED` and say so.

**Leakage re-audit:**
> Re-run the full leakage suite from Stage 6 against the current pipeline, including any statistic,
> threshold, or vocabulary fitted since then. Report which fitted objects saw which splits.

**Scope control:**
> List everything built that is not required by the architecture document. For each: justify it or
> propose removing it. The architecture explicitly cuts unnecessary components.

**Honest status:**
> Update `PROJECT_STATUS.md`. In `KNOWN ISSUES`, list everything currently broken, unverified, or
> assumed. Do not omit anything to make the status look better.

---

## APPENDIX B — Stage → Week Mapping

The architecture's 8-week plan, mapped to these stages:

| Week | Stages | Deliverable |
|---|---|---|
| 1 | S0–S4 | `ANSWER_GRAMMAR.md`, taxonomy, data pipeline, licence audit |
| 2 | S5–S8 | **Oracle accuracy + oracle BLEU (GATE 1)** |
| 3 | S9–S13 | **Transfer factor (GATE 2)** |
| 4 | S14–S16 | **Falsification test (GATE 3)**, M3/M4/M5 |
| 5 | S17–S18 | CDVQA accuracy, ECE, risk–coverage |
| 6 | S19–S23 | Europe result and **India result (GATE 4)** side by side |
| 7 | S24–S25 | Ablations, bootstrap CIs, McNemar, error analysis, PDF report |
| 8 | S26 | Freeze, rehearse, finalise limitations and presentation |

The architecture names uncontrolled feature development as one of the largest project risks.
Week 8 means **freeze**, not "one more model".
