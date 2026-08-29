# SatQuery — Implementation Map

**Status:** Stage 1 deliverable — architecture comprehension. No code written, no metric measured.
**Date:** 2026-08-29
**Sources read in full for this document:**
- `docs/architecture/SatQuery_Architecture (1) (1).pdf` — 28 pp., 133 numbered points. **This is Architecture B** and it already incorporates the review's corrections (its §2.1 is "The Biggest Correction: 19 Classes vs. 44 Classes"). Cited below as **[PDF §n]**.
- `docs/architecture/SatQuery_Architecture_Review_v2 (2).md` — 1,622 lines. The critical review of the *previous* architecture (Architecture A, `SatQuery_AI_Architecture.pdf`, 58 pp.) that produced Architecture B. Contains the detailed per-model specifications the PDF summarises. Cited as **[REV §n]**.
- `CLAUDE.md` — standing project rules. Cited as **[CM §n]**.

### Evidence labels used throughout

Inherited from [REV §0], extended with the labels required by [CM §5]:

| Label | Meaning |
|---|---|
| **VERIFIED** | The review author read the primary source and confirmed it. |
| **PUBLISHED** | A number transcribed from a paper table the review author read. |
| **PRIOR** | An engineering expectation. Not measured. Falsifiable. |
| **SPEC** | Stated by the architecture documents as a design decision. |
| **DERIVED** | My inference from the documents, logically forced but not written down. |
| **ASSUMPTION — REQUIRES VALIDATION** | My inference that is *not* forced and could be wrong. |
| **UNKNOWN** | Genuinely unresolved in both documents. Needs a human decision. |

**No accuracy number in this document is a target.** Every number is either PUBLISHED (with source) or explicitly absent. Per [CM §11], targets do not exist until the gate measurements exist.

---

## 1. Complete architecture understanding

### 1.1 What the system does

SatQuery receives one or two GeoTIFFs plus an English question, and returns a structured JSON answer with a confidence score, a visual evidence overlay, and an append-only execution trace [PDF §1, §79].

### 1.2 The nine stages

Both documents describe the same nine-stage pipeline [PDF §6 diagram; REV §2.2]:

| # | Stage | Component(s) | Nature |
|---|---|---|---|
| 1 | **Validation** | V1 | Deterministic |
| 2 | **Preprocessing** | P1 | Deterministic |
| 3 | **Query understanding** | Q1, M10 (fallback) | Deterministic rules; probabilistic fallback |
| 4 | **Routing** | R1 | Deterministic |
| 5 | **Perception** (the learned layer) | Scene cache, M1, M5, M6 | Probabilistic |
| 6 | **Symbolic computation** | M2 | Deterministic (fitted parameters) |
| 7 | **Answer-format decision** | M3, M4, M7 | Probabilistic |
| 8 | **Confidence** | M9 + abstention policy | Probabilistic → deterministic policy |
| 9 | **Assembly and evidence** | A1 + four output artifacts | Deterministic |

Stages 1–4 turn an untrusted upload and a free-text string into a validated, typed execution plan. Stage 5 is the only place where a neural network looks at pixels. Stage 6 is where the answer's *number* is produced. Stages 7–8 convert that number into the benchmark's required answer format and attach a calibrated reliability estimate. Stage 9 renders it and records how it was obtained.

### 1.3 The perception / measurement / language separation

[PDF §133] names this the most important conceptual distinction in the project:

```
PERCEPTION    what is in the image?              M1, M5, M6 (and M7 when necessary)
     ↓
MEASUREMENT   what does the image mathematically imply?    M2 — and M2 only
     ↓
DECISION      what answer format does the benchmark want?  M3, M4, M5
     ↓
CONFIDENCE    how much should this be trusted?             M9
     ↓
LANGUAGE      how do I express it?                         M7, M8
```

The separation is enforced by two rules that are architecturally load-bearing, not stylistic:

**Rule 1 — the number-flow rule** [CM §2; PDF §78; REV §2.3]. `Image → M1 → M2 → NUMBER → assembler`. A language model may *phrase* an answer; it may never *produce the numerical value* in it. Numbers are substituted into templates. Parsing a number back out of generated text is a bug by definition.

**Rule 2 — typed structures only** [REV §2.3]. No model consumes another model's natural language. M7 receives a structured attribute dictionary from M2, never a sentence from another component. The chain `M1 → sentence → M7 → sentence → M3` is explicitly forbidden [CM §2]. Models write into a shared typed scene representation that M2 reads; they are hierarchical, not peer-to-peer.

Together these are what make the execution trace mean anything. If a number could originate in generated text, the trace would record a derivation that did not actually produce the answer.

### 1.4 Why predict a map and calculate, rather than ask a VLM

This is the project's central bet, and the justification is **not** a claim about model quality. It is a claim about how the benchmark's ground truth was manufactured.

**The benchmark's own construction is the argument** (VERIFIED, [REV §1.1] from §3.1 of arXiv:2603.29630):

> Captions are built by extracting presence, per-class contiguous-region counts, per-class and per-instance sizes, and pairwise adjacency **directly from the pixel-level reference maps**, with areas rounded to the nearest 1000 m² and classes tiered by coverage (>25% primary, 5–25% secondary, <5% marginal). Binary and MCQ annotations are generated from those same four spatial categories. Referring expressions are generated from instance geometry with explicit area and bbox-fill constraints.

So the ground-truth answer to "how much forest is there?" was *not* written by a human looking at an image. It was computed by a program that ran over a CORINE reference map. The answer is a deterministic function of a pixel-level map.

That has a direct architectural consequence: **the task is not perception, it is measurement** [REV §1.1]. Reproducing the generator's process — predict the map, then run the same measurement — is structurally aligned with how the target was produced. Asking a generative model to *guess* the output of a deterministic program is strictly harder than *running* that program on a predicted input.

**The published evidence that the field currently gets this wrong** (PUBLISHED, [REV Appendix A], Table 3):

| Model | Adjacency (balanced yes/no) |
|---|---|
| Best evaluated RS-specific model (EarthMind, RGB) | 55.97 |
| Frontier general model (reported ~2T params) | **55.86** |
| Qwen3-VL-8B | 58.45 |

A model with a reported two trillion parameters reaches 55.86% on a *balanced* yes/no question about whether two land-cover regions touch — under six points above chance. `scipy.ndimage.binary_dilation` computes the same relation exactly, in microseconds, given a correct map [PDF §120].

The argument to make on stage is explicitly **not** "our smaller network is smarter" [PDF §120]. It is: *we changed the problem formulation. Once perception is separated from deterministic spatial measurement, some tasks no longer require generative reasoning at all.*

### 1.5 The second, stronger argument — Indian adaptability

[REV F7] identifies an argument the previous architecture never made, and rates it more important than the leaderboard argument:

- In a **VLM-only** design, the Indian domain gap is distributed across a model that can only be adapted with Indian image–text pairs. **No such corpus exists.** There is no Indian BigEarthNet.txt. You cannot LoRA your way to India without Indian instruction data.
- In the **segmentation-plus-symbolic** design, the entire Indian gap is concentrated in *one* model — M1 — which can be adapted with Indian pixel labels, which are free (ESA WorldCover, Dynamic World, Bhuvan).
- M2 requires **no adaptation at all**. `binary_dilation` and `scipy.ndimage.label` are geography-invariant by construction. Area is pixel count × GSD² in Bengaluru exactly as in Bavaria [REV §5.2].

So the claim is: *symbolic is the only one of the two designs that is adaptable to India at all, because it localises the entire domain shift into the one component for which Indian supervision exists.*

### 1.6 What the architecture does **not** claim

Stated explicitly so it is not lost [PDF §121–122]:

- The geometry engine cannot recover information M1 failed to segment. If M1 is wrong, M2 is wrong, and the answer is wrong.
- The architecture does not claim symbolic reasoning solves everything. The oracle measurement tells us the symbolic *ceiling*; the transfer factor tells us how much segmentation costs.
- The Indian **sensor** gap (Cartosat-2S / RISAT) is not measurable with obtainable data, and no number for it may ever be fabricated [PDF §122; REV §5.6 rule 6].

---

## 2. Complete component inventory

### 2.1 Pipeline components (non-model)

| ID | Name | Stage | One-line purpose |
|---|---|---|---|
| **V1** | Input validator | 1 | `rasterio`-based check of band count, dtype, CRS, geotransform, shape, NoData, modality, pair co-registration, and metadata-string sanitisation → emits `InputManifest` or a typed rejection [PDF §7]. |
| **P1** | Sensor normalisation | 2 | S1 linear→dB→z-score; S2 20 m→10 m bilinear, 60 m discarded, z-score; both using **frozen training-split statistics**; emits the band-presence mask [PDF §8–10]. |
| **Q1** | Intent + argument parser | 3 | Rule-based parse over the closed template set → `(intent, class_a@level, class_b@level, qualifier)`; CLC synonym table resolves words to class IDs at any hierarchy level [PDF §11–12]. |
| **R1** | Deterministic router + frozen tool registry | 4 | Lookup `(intent × input_config) → ordered tool plan`; parameters bound and Pydantic-validated; no LLM planner, no `eval()`, no dynamic plugin loading [PDF §14–15]. |
| **Scene cache** | Scene cache | 5 | Keyed on `hash(scene_bytes) + model_version`; map computed once per scene, serves unlimited queries; a map from a different checkpoint is never served [PDF §17]. |
| **A1** | Answer assembler | 9 | Substitutes M2's number into a template, attaches unit/confidence/evidence refs; enforces the number-flow rule [PDF §78]. |

### 2.2 Models M1–M10

| ID | Name | One-line purpose |
|---|---|---|
| **M1** | Multi-sensor LULC segmenter | Convert 12-channel S1+S2 into a 44-class CORINE-L3 pixel map — the map every symbolic answer is computed from; **the only component carrying the Indian domain gap**. |
| **M2** | Hierarchy-aware symbolic geometry engine | Compute presence, count, area, adjacency, relative position, referring box/point, and caption attributes exactly from a class map. Deterministic; **no neural network** [CM §1]. |
| **M3** | Binary VQA decision head | Given a computed quantity, a stated quantity and uncertainty signals, decide YES/NO under a *fitted* tolerance rather than exact comparison. |
| **M4** | MCQ option scorer | Select one of four options by fitted-metric distance (log scale for area, rank for count) + softmax; uses M5 posteriors for the metadata sub-tasks. |
| **M5** | Scene metadata classifier | Predict country / season / Köppen climate zone from pixels — the 3 of 8 MCQ sub-categories geometry cannot touch. |
| **M6** | Siamese semantic change model | Produce semantic maps for both dates plus a change mask, from which a from-to transition matrix `T[i][j]` is computed. |
| **M7** | VLM (InternVL3-1B + LoRA) | Free-form language, captioning, change narration, RS-adaptation compliance, and the low-confidence fallback. **Not** counting, area, adjacency, position or boxes. |
| **M8** | Template→style caption rewriter | Rewrite a factually-exact template caption into the dataset's paraphrased surface style. **Conditional — built only if the week-2 gate says so.** |
| **M9** | Confidence calibrator | Map internal signals to a calibrated `P(answer correct)`; logistic regression + isotonic. |
| **M10** | Query intent classifier | 8-way TF-IDF → linear SVM classification of a free-text query, on CPU, when Q1's rules fail. |

### 2.3 Layers, task types, datasets, services, evaluation and security

**Task types.** [PDF §13] states M10 performs **8-way** classification and that "the eight task categories correspond to the query types handled by the architecture" — but **the eight are never enumerated** in either document. Separately, BigEarthNet.txt is described as spanning **15 tasks** [REV §4.2] and the task vocabulary is called "closed at 15 tasks" [REV §1.4]. See §10.2 — this is an open ambiguity.

**Datasets** (full matrix in §4):

| Dataset | One-line purpose |
|---|---|
| **reBEN** (BigEarthNet v2.0) imagery + CLC-L3 reference maps | M1's supervision. The only dataset supplying pixel-level CORINE L3 at the benchmark's exact patch geometry. |
| **reBEN metadata** | M5's supervision — country, acquisition date, geolocation, S2 tile ID. Free labels. |
| **BigEarthNet.txt annotations** | The answer grammar and the scoring target; M3/M4/M7/M8 supervision. |
| **BigEarthNet.txt benchmark split** | **Quarantined.** 1,082 pairs / 15,029 annotations. Evaluation only, touched once. |
| **SECOND** | M6's supervision — bi-temporal semantic change masks over 6 classes. |
| **CDVQA** | Change-path scoring; auto-generated from SECOND's masks; closed answer set of 19 categories. |
| **VRSBench** | Mandated grounding evaluation; also the only legally obtainable sub-metre imagery → scale-consistency signal only. |
| **RSVQA (LR + HR)** | Mandated VQA evaluation. **Evaluation only — never train on it.** |
| **Sentinel-1/2 over India** | The imagery half of BHARAT-EO — identical sensors/bands/GSD to reBEN, differing only in geography. |
| **ESA WorldCover 10 m v200** | Primary Indian weak pixel labels (11 classes, CC-BY). |
| **Google Dynamic World V1** | Indian weak labels with per-pixel probabilities → confidence weighting. |
| **Bhuvan LULC (NRSC/ISRO)** | Independent coarse Indian cross-check; politically valuable in front of ISRO judges. |
| **Bhoonidhi (Resourcesat/RISAT ≥5 m)** | Unlabelled Indian-sensor domain-shift measurement only. |
| **BHARAT-EO / BHARAT-TRAIN / BHARAT-VAL** | The corpus we build. BHARAT-VAL is held out, never trained or tuned on, used once. |
| **Cartosat-2S / RISAT hidden set** | **Unobtainable.** Never claim a number for it. |

**Services / runtime.** Scene cache; append-only trace store; evidence overlay renderer; PDF report generator; JSON response API; frontend (map, overlay, trace panel, evidence panel — nothing more [REV §7.4]).

**Evaluation components.** Oracle harness (M2 on ground-truth maps); blind question-only baseline; majority-class baseline; class-prior baseline; the A1 falsification ablation (six configs); perturbation suite (8 rows); bootstrap CI machinery (resampled over the 1,082 *pairs*, not annotations); McNemar's paired test; per-class IoU table; 44×44 confusion matrix with sibling groups boxed; count-error decomposition (over- vs under-count); per-sub-task error attribution; ECE / Brier / reliability diagram / risk–coverage curve.

**Security components.** V1's typed rejection and metadata-string sanitisation; Q1/M10 input sanitisation (control characters stripped, length capped) as a **prompt-injection defence**, since metadata strings from uploaded files can reach that path [REV §3.10]; deterministic routing with no `eval()` and no dynamic plugin loading; Pydantic bounds validation on every bound tool parameter; append-only trace; benchmark-split loader guard raising unless `ALLOW_BENCHMARK_EVAL=1` [CM §7].

---

## 3. End-to-end data flow, per query family

**Note on the count.** The Stage-1 prompt asked for "seven query families" and then listed nine items. Both documents support **nine distinct symbolic operations** [PDF §132 fact 7; REV §2.2 stage 6]. All nine are traced below. See §10.2 for the naming reconciliation this needs.

### 3.0 The common prefix

Every single-image query runs:

```
GeoTIFF(s) + question
  → V1   validate → InputManifest (or typed rejection)
  → P1   S1 dB+z-score · S2 resample+z-score · band-presence mask
  → Q1   rules → (intent, class_a@level, class_b@level, qualifier)
           └─ on rule failure → M10 (TF-IDF → SVM, 8-way, CPU)
  → R1   (intent × input_config) → Pydantic-validated tool plan + trace header
  → SCENE CACHE  hit → reuse map · miss → run Stage-5 perception
```

Then the family-specific path. Every family terminates:

```
  → M9   P(answer correct) → high/medium/low band
  → abstention policy   operational: abstain below τ · benchmark: NEVER abstain
  → A1   number from M2 substituted into template
  → JSON + evidence overlay + execution trace + PDF report
```

### 3.1 Component firing matrix

`●` fires · `○` idle · `◐` conditional · `▲` fires but its output is unused

| Family | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 |
|---|---|---|---|---|---|---|---|---|
| **(a) Area** | ● | ● | ◐ binary | ◐ MCQ | ○ | ○ | ◐ fallback | ○ |
| **(b) Count** | ● | ● | ◐ binary | ◐ MCQ | ○ | ○ | ◐ fallback | ○ |
| **(c) Presence** | ● | ● | ◐ binary | ◐ MCQ | ○ | ○ | ◐ fallback | ○ |
| **(d) Adjacency** | ● | ● | ◐ binary | ◐ MCQ | ○ | ○ | ◐ fallback | ○ |
| **(e) Relative position** | ● | ● | ◐ binary | ◐ MCQ | ○ | ○ | ◐ fallback | ○ |
| **(f) Referring expression / point** | ● | ● | ○ | ○ | ○ | ○ | ◐ fallback | ○ |
| **(g) Metadata MCQ** | ▲ | ○ | ○ | ● | ● | ○ | ○ | ○ |
| **(h) Caption** | ● | ● | ○ | ○ | ? | ○ | ◐ | ◐ gated |
| **(i) Change** | ○ | ● | ● | ● | ○ | ● | ◐ narration | ○ |

M9 and A1 fire for all nine. V1/P1/Q1/R1/cache fire for all nine.

---

### (a) AREA — "What is the area of forest in this image?"

```
[common prefix, intent=AREA, class=FOREST@level]
  → M1  12×120×120 → logits[44,120,120] + 8× TTA → argmax_map[120,120]
  → M2  step 0  aggregate L3(44) → the CLC level the question asked
         step 1  binary mask for the aggregated class
         step 2  morphological cleanup (opening, hole fill) — FITTED params
         step 5  regionprops → per-instance area
         area = Σ pixels × GSD², rounded to nearest 1000 m²   (VERIFIED rounding)
  → M3 (binary "is there ~45,000 m² of forest?") or M4 (MCQ, 4 options)
  → M9 → A1 → JSON{value: 420000, unit: "m²", confidence, evidence_refs}
```
**Idle:** M5, M6, M8, and M7 unless M9 drops below τ_low in benchmark mode.
**Robustness:** highest of all operations [REV F2] — area integrates over thousands of pixels, so unbiased per-pixel errors average out.
**Open:** whether components dropped by the MMU threshold are excluded from the area sum is **not specified**. See §10.2.

### (b) COUNT — "How many water regions are there?"

Identical prefix and perception. M2 differs in that **steps 2–4 are load-bearing**:

```
  → M2  step 0  aggregate to the queried level   ← CRITICAL (see §5.3)
         step 1  binary mask
         step 2  morphological opening — FITTED kernel
         step 3  connected components — FITTED connectivity (4 vs 8)
         step 4  drop components below FITTED minimum mapping unit
         count = |components|
  → M3 / M4 → M9 → A1
```
**Robustness:** **lowest** of all operations [REV F2]. A single spurious 3-pixel blob changes the answer; a single thin misclassified bridge merges two regions into one. Counting has no averaging.
**Why aggregation must precede components:** counting "how many artificial-surface regions" on an L3 map requires merging L3 siblings into one binary mask *before* running connected components — otherwise a city split into continuous and discontinuous urban fabric counts as two regions when the ground truth says one [REV F1].

### (c) PRESENCE — "Is there coniferous forest in this image?"

```
  → M2  aggregate → mask → components → presence = |components| > 0
  → M3 / M4 → M9 → A1
```
**Robustness:** medium — bounded directly by CLC *sibling confusion*, which is exactly what the benchmark's adversarial "no" answers target (VERIFIED, [REV F1/§3.1]). This is where the multispectral bands earn their keep and an RGB-only competitor loses.

### (d) ADJACENCY — "Are forest and water adjacent?"

```
  → M2  aggregate both classes → mask_A, mask_B
         adjacent = binary_dilation(mask_A, k) ∩ mask_B ≠ ∅     (k FITTED)
  → M3 / M4 → M9 → A1
```
**Idle:** M5, M6, M8. **M7 does not need to answer the question at all** [PDF §125].
**Robustness:** high — needs only that both classes exist roughly in the right places.
This is the demonstration family: PUBLISHED 55.86% for a ~2T-parameter model vs an exact computation.

### (e) RELATIVE POSITION — "Which region is north of the agricultural area?"

```
  → M2  aggregate both → centroids → sign of centroid delta → 8-way compass
  → M3 / M4 → M9 → A1
```
**Robustness:** high — centroids are averages, robust for the same reason as area.

### (f) REFERRING EXPRESSION / POINT

Two separate benchmark tasks [REV §0.1D]. Both output a **bounding box, not a scalar**, so **M3 and M4 stay idle** (DERIVED — there is no option set and no yes/no decision to make).

```
Referring LULC detection: "the largest forest region"
  → M2  components → regionprops
         filter: 1% ≤ instance area ≤ 50% of image  AND  bbox_fill ≥ 40%   (VERIFIED)
         → argmax / argmin by qualifier → bbox
Referring point detection: given a point inside the target, predict the enclosing box
  → M2  bbox of the connected component containing the given point
```
**Referring point is near-trivial** — one line of `scipy.ndimage` — and Architecture A left it on the table entirely [REV §0.1D].
**Robustness:** medium — needs the *correct instance*, not just the correct class; selection error is unforgiving. But the 1–50% area and ≥40% bbox-fill filters remove wrong candidates for free.
**M7** may fire in fallback with grammar-constrained box decoding.

### (g) METADATA MCQ — "Which country was this image acquired in?"

**M1 and M2 are irrelevant to this family** [PDF §127].

```
  → R1  (MCQ + country) → M5 → M4 → M9 → answer
  → M5  ConvNeXt-Tiny, 12-ch stem, 3 heads → 3 posteriors
  → M4  restrict the posterior to the four offered options → argmax
  → M9 → A1
```
**Idle:** M2, M3, M6, M7, M8. M1 is marked **▲** because on a cache miss the Stage-5 perception block may compute it in parallel [PDF §6 diagram], but **its output is not used for this answer** (DERIVED).
**Gate:** if the evaluation harness supplies country/season/geolocation alongside each annotation, these become lookups and **M5 is discarded entirely** [PDF §55; REV §3.5]. This must be checked in week 1 from the parquet. Open question #2 in §10.1.

### (h) CAPTION — "Describe the image."

```
  → M1 → M2  caption attribute struct:
              presence · per-class contiguous-region counts ·
              per-class and per-instance sizes · pairwise adjacency ·
              tiers: primary >25% · secondary 5–25% · marginal <5%   (VERIFIED)
  → template caption (facts originate here, and only here)
  → M8 if the week-2 gate says build it, else M7        ← style only
  → M9 → A1
```
**Facts originate from M2; language style comes from M7/M8** [PDF §128]. This is the number-flow rule applied to captioning.
**Idle:** M3, M4, M6.
**M5:** marked **?** — season, country and Köppen zone are appended during the *reference* caption generation from external maps (VERIFIED, [REV F4]), but neither document wires M5's posteriors into our caption path. ASSUMPTION — REQUIRES VALIDATION. See §10.2.
**The gate that decides M8's existence** [REV §3.8], run in week 2 on ground-truth maps, no trained model needed:

| Oracle caption BLEU-4 | Decision |
|---|---|
| ≥ ~35 | Raw templates suffice — **skip M8 entirely** |
| ~10 – ~35 | **Build M8** — where the review expects to land (PRIOR) |
| < ~10 | Drop the symbolic captioning path — route to M7 |

### (i) CHANGE — "What changed between image 1 and image 2?"

The only family with two images, and the only one where **M1 does not fire**.

```
  → V1  additionally performs the pair co-registration check
  → M6  Siamese U-Net, shared encoder
         → map_t1[6,H,W], map_t2[6,H,W], change_mask[H,W]     (SECOND 6-class taxonomy)
         → T[i][j] = |{p : change[p]=1, M1[p]=i, M2[p]=j}|     from-to transition matrix
  → M2  arithmetic over T — counts, argmax transitions, deltas
  → M3 / M4  (CDVQA's closed 19-category answer set)   [PDF §129]
  → M9 → A1
```
**Idle:** M1, M5, M8. **M7** optionally fires for change *narration* (curriculum step 3, [REV §3.7]).
**Why M1 is idle:** M6 uses a different taxonomy (SECOND-6, not CORINE-44) on different imagery (0.5–3 m aerial RGB, not 10 m S1+S2). The two paths do not share a map (DERIVED, forced by [REV §3.6/§4.2]).
**Structural point:** the change path is the same thesis repeated — perception (M6) → measurement (M2 over T) → answer. Change VQA is arithmetic over a predicted transition matrix, exactly as the main path is arithmetic over a predicted LULC map [REV §0.1B, VERIFIED].
**Open:** M6's specified input is RGB 512×512 from SECOND, but the deployment/hidden-set input is a co-registered optical+SAR GeoTIFF pair. The bridge between these is not specified. See §10.2 — this is a significant gap.

---

## 4. Model & dataset matrix

| Component | Model / method | Dataset | Input (shape / type) | Output (shape / type) | Metric | Training strategy | Purpose |
|---|---|---|---|---|---|---|---|
| **V1** | `rasterio` checks | — | 1–2 GeoTIFFs + str | `InputManifest` \| typed rejection | Rejection correctness on malformed inputs | None | Reject bad input before it corrupts everything downstream |
| **P1** | Deterministic normalisation | reBEN train statistics (frozen, versioned, hashed) | Raw bands | `float32[12,120,120]` + `band_presence[10]` | — | Statistics **fitted on train split only** | Put both sensors on a comparable, leak-free scale |
| **Q1** | Rules over closed templates + CLC synonym table | Benchmark templates | `str` (sanitised) | `(intent, class_a@level, class_b@level, qualifier)` | Parse success rate | None (rules) | Turn text into a typed query |
| **M10** | TF-IDF (word+char n-grams) → linear SVM | ~300 human-paraphrased + auto-generated template permutations | `str` | task label + confidence | Accuracy, **target ≥98%** | From scratch (seconds, CPU) | 8-way intent fallback when rules fail |
| **R1** | Frozen registry lookup + Pydantic | — | `(intent, input_config)` | Ordered tool plan + trace header | Plan validity | None | Deterministic, auditable execution path |
| **M1** | Dual-encoder U-Net, ConvNeXt-V2-Tiny ×2, 1×1 conv fusion + SE gate, ~30–45M params | reBEN, 229,114 train patches (geographic split) | `float32[12,120,120]` | `logits[44,120,120]` + `argmax_map` + per-pixel top-1 margin | **Downstream symbolic accuracy (primary)**; mIoU @L3-44 / @19 / @coarse-7; per-class IoU; 44×44 confusion matrix; 8-row perturbation table | **FROM SCRATCH** — AdamW lr 3e-4, wd 1e-4, cosine + 5% warm-up, bf16, batch 128, 30–50 epochs; 8× TTA at inference | Produce the map every symbolic answer is computed from |
| **M2** | `scipy.ndimage` + `skimage.measure`. **No neural network.** | Ground-truth maps (week 2) → predicted maps (week 5) | `argmax_map[120,120]` + taxonomy YAML | Typed struct: scalar + per-instance properties | **Oracle exact-match vs released annotations. Target ≥99%** on presence/area/adjacency/rel-pos | **FIT** connectivity, MMU, opening kernel, dilation radius — twice (GT maps, then predicted maps) | Compute what can be computed; geography-invariant |
| **M3** | LightGBM (~200 trees, depth 4) or L2 logistic regression | BigEarthNet.txt train annotations, **features from PREDICTED maps** | 12 tabular features (computed, stated, log-ratio, rank-diff, subtype, class, pixel share, class margin, TTA σ, near-MMU count, sibling prior) | `P(yes)` | Accuracy per sub-type (Table 3 layout), ROC-AUC, **ECE**, McNemar vs fixed threshold | **FROM SCRATCH**, class-balanced to match the benchmark | Decide YES/NO under a fitted tolerance, and learn to correct M1's systematic biases |
| **M4** | Fitted-metric distance + softmax (log scale for area, rank for count) | Same | Computed value, 4 parsed options, sub-category, M5 posteriors | argmax option + softmax distribution | Accuracy per sub-task (Pr/A/Cnt/Adj/RP/Loc/S/Clt), instruction-following (100% by construction) | **FIT** a handful of parameters | Select an option; never generate one |
| **M5** | ConvNeXt-Tiny, 12-ch stem, 3 linear heads, ~28M params | reBEN metadata (country, date, geolocation) + Köppen lookup from a public 1 km raster | `float32[12,120,120]` | 3 posteriors: country (10), season (4), Köppen (k) | Top-1 per attribute; **derived 4-option MCQ accuracy** (what is actually scored) | **TRANSFER** — ImageNet-init on RGB channels, full fine-tune, a few GPU-hours | Solve the 3 of 8 MCQ sub-categories geometry cannot touch |
| **M6** | Siamese U-Net, **shared** ImageNet-pretrained encoder (ResNet-34 / ConvNeXt-Tiny), 3 heads. Refs: Bi-SRNet, SCanNet | SECOND (2,968 public pairs) → CDVQA official test splits | T1, T2 RGB 512×512 | `map_t1[6,H,W]`, `map_t2[6,H,W]`, `change_mask[H,W]` → `T[i][j]` | SECOND mIoU / SeK / F1; CDVQA official test accuracy; **mandatory question-only blind baseline** | **TRANSFER** — ImageNet-init, full fine-tune (data-poor: ~1,600 train pairs) | Make change VQA arithmetic over T |
| **M7** | `OpenGVLab/InternVL3-1B` (MIT; Qwen2.5-0.5B base, Apache-2.0) + frozen BEN S1/S2 ViT branches + trainable linear projections + **LoRA r=8, α=32, dropout=0.1** → 5.8M trainable of 1.1B | BigEarthNet.txt captioning subset (stratified subsample — **report the fraction**) | S1/S2/RGB tokens + instruction tokens | Text, under **constrained decoding** | BLEU-4 / ROUGE / METEOR / CIDEr / BERTScore / SBERT-cosine (Table 7 layout) + instruction-following rate | **PEFT.** Curriculum: (1) projections only ~2k steps, (2) joint LoRA + projections on captioning. Do **not** train VQA/MCQ/grounding adapters unless the week-4 gate fails | Language, captioning, RS-adaptation compliance, low-confidence fallback |
| **M8** | Flan-T5-base (250M) seq2seq, or LoRA on Qwen2.5-0.5B-Instruct | (our template caption, released caption) pairs — free and exactly aligned | Template caption string | Styled caption string | BLEU-4 / ROUGE / METEOR / CIDEr **+ automated factuality check** (re-extract attributes; they must match) | **FINE-TUNE.** Conditional on the week-2 gate | Match the dataset's paraphrased surface style without touching the facts |
| **M9** | L2 logistic regression → isotonic regression | Held-out **calibration split** (not train, not benchmark) | 7 features (class margin, TTA answer stability, component-count σ, area interval width, min component margin, band-presence fraction, sibling-confusion prior) | `P(correct)` + high/med/low band | **ECE**, Brier, reliability diagram, **risk–coverage curve** | **FIT.** Refitted on BHARAT-VAL before any Indian confidence claim | Turn "confidence" from a claim into a measured quantity |
| **A1** | Template substitution | — | M2 scalar + M9 confidence | JSON + evidence + trace + PDF | — | None | Enforce: LM may phrase, never produce, the number |

### 4.1 The pretraining decision table — and why it differs per model

[PDF §116] flags this as a distinction to memorise. It is a deliberate, defensible asymmetry:

| Model | Decision | Reason |
|---|---|---|
| M1 | **From scratch** | 229k labelled patches = **data-rich**; classification pretraining costs spatial precision and forces a 3-vs-12 channel mismatch |
| M5 | Transfer (ImageNet) | Scene-level classification — exactly what ImageNet features are good for |
| M6 | Transfer (ImageNet) | ~1,600 training pairs = **data-poor** |
| M7 | PEFT (LoRA) | 1.1B params; full fine-tuning infeasible on one GPU; published recipe |
| M8 | Fine-tune | Small seq2seq, abundant free aligned pairs |
| M3 / M4 / M9 / M10 | From scratch / fit | Seconds to minutes to train |
| M1 → India | **Staged fine-tune with replay — NOT LoRA** | M1 is only 30–45M params; there is no memory problem for LoRA to solve, while its low-rank constraint is a real cost [REV §5.5] |

**M1 from scratch and M6 from pretrained, same team, same week, opposite decisions, for a stated reason.** [REV §3.6] notes this asymmetry is the kind of thing a judge probes.

---

## 5. Dependency & error-propagation map

### 5.1 Determinism marking

| DETERMINISTIC | PROBABILISTIC |
|---|---|
| V1 · P1 · Q1 (rules) · R1 · **M2** · scene cache · abstention policy · A1 · evidence/trace/PDF renderers | M1 · M3 · M4 · M5 · M6 · M7 · M8 · M9 · M10 |

M2 is deterministic **in its logic** while its *parameters* (connectivity, MMU, opening kernel, dilation radius) are fitted from data [REV §3.2]. That distinction matters: a fitting error is silent and systematic, not random.

### 5.2 Dependency graph

```
V1 ──► P1 ──► [M1, M5, M6]          (V1/P1 failure ⇒ total failure)
       Q1 ──► R1 ──► tool plan       (parse/route failure ⇒ wrong path, wrong answer)
        └── M10 (fallback only)

M1 ──► M2 ──► M3 ──┐
        ▲     M4 ──┤
        │          ├──► M9 ──► A1 ──► JSON / evidence / trace / PDF
M6 ──► T ┘   M7 ──┤        ▲
                   │        │
M5 ──► M4 ─────────┘        │
M1 (margin, TTA variance) ──┘
M2 ──► M7 (attribute struct, JSON — never a sentence)
M2 ──► M8 (template caption)
```

### 5.3 Where an upstream error becomes unrecoverable

Ordered by how much damage it does. **Silent** means nothing downstream can detect it.

| # | Failure | Propagates to | Recoverable? | Why |
|---|---|---|---|---|
| 1 | **Loading GeoTIFFs with PIL / OpenCV / `imread`** | Everything | **No — silent and catastrophic** | Silently drops bands beyond 4, silently rescales 16-bit to 8-bit, silently discards CRS and geotransform. Areas come out wrong **by a constant factor** and nothing detects it. [REV §6.1] calls this the most common way a student team quietly ruins a geospatial project. Guarded by V1 + [CM §1]. |
| 2 | **Wrong hierarchy aggregation table** (M2 step 0) | Count, presence, adjacency, rel-pos, ref-exp, caption | **No — silent and systematic** | Counting on un-aggregated L3 splits a city into continuous + discontinuous urban fabric → 2 regions where truth says 1. Loses the counting sub-task **systematically**, not noisily [REV F1]. |
| 3 | **M1 segmentation error** | M2 → M3/M4 → M9 → A1 | **No** — but *quantified* | "If M1 is wrong, M2 is wrong, and the answer is wrong — the geometry engine can't recover information that wasn't correctly segmented" [PDF §121]. This is why the oracle decomposition exists: it measures exactly this cost per sub-task. Partially compensated by training M3/M4 on **predicted** maps so they learn M1's biases [REV F3]. |
| 4 | **Normalisation statistics computed per-image or per-batch** | M1, M5 | **No — silent** | Leaks, and breaks at single-image inference. Must be frozen train-split statistics, versioned and hashed into the model card [REV §6.1]. |
| 5 | **Wrong connectivity (4 vs 8) or MMU** | Count (everything), presence (marginally) | **No — silent and systematic** | "Swings **every** counting answer" [REV §3.2]. One afternoon of fitting prevents it. |
| 6 | **Q1 / M10 misclassifies intent** | Whole tool plan | **No** | R1 executes the wrong plan deterministically and confidently. M10's ≥98% target exists for this reason. |
| 7 | **M6 consistency loss omitted or mis-weighted** | `T[i][j]` → all change answers | **No** | Without the consistency term the three heads disagree and "the transition matrix is nonsense" [REV §3.6]. |
| 8 | **Random (non-geographic) validation split** | Every architecture decision made with it | **No — silent and optimistic** | Adjacent 1.2 km patches are strongly spatially autocorrelated; validation mIoU comes out several points optimistic and you make wrong decisions with a biased instrument [REV F11]. |
| 9 | **Tuning on the benchmark split** | Every reported number | **No** | The number will not survive the hidden set. Guarded by the `ALLOW_BENCHMARK_EVAL=1` loader guard [CM §7]. |
| 10 | **Mixup / CutMix augmentation** | Count, ref-exp, adjacency | **No** | Fabricates region boundaries and changes connected-component counts — destroys the exact topology the symbolic path depends on. Explicitly forbidden [CM §1; REV §6.4]. |
| 11 | M5 error | Metadata MCQ only | Bounded | Contained to 3 of 8 MCQ sub-categories; cannot touch the geometric path. |
| 12 | M7 / M8 error | Caption surface form; fallback answers | **Yes — bounded by design** | The number-flow rule means a language error cannot corrupt a number. M8 regressions are caught by the automated factuality check. |
| 13 | M9 miscalibration | Abstention decisions, fallback rate | Yes | In benchmark mode the system never abstains, so miscalibration costs ranking, not answers. |

**The structural observation:** failures 1, 2, 4, 5, 8, 9 are all **silent** — they produce confident, well-formed, wrong answers with a clean-looking trace. Every one of them is a *convention* or *plumbing* error, not a model error. This is why weeks 1–2 are spent on the parquet, the taxonomy YAML and the fitting sweeps before a single GPU hour is spent.

---

## 6. Implementation plan

### 6.1 The build order

From [PDF §117] / [REV §8.2]. The architecture documents use an **8-week** plan; `CLAUDE.md` §11 refers to a finer **stage** numbering (S8, S13, S16, S23) that does not appear in either document — see §10.2.

| Week | Build | Gate — the number that must exist by Friday |
|---|---|---|
| **1** | Data pipeline (reBEN → LMDB). **Parse the parquet:** answer grammar, taxonomy level, distractor spacing, metadata fields. Taxonomy YAML + class-mapping layer. Evaluation harness skeleton. Licence audit. | `docs/ANSWER_GRAMMAR.md` exists and answers: which CLC level do questions use; what metadata rides along; how are distractors spaced |
| **2** | **M2 geometry engine against ground-truth maps.** Fit connectivity / MMU / opening / dilation. **Run the captioning oracle.** Run blind + majority baselines. Start BHARAT-EO collection. | **GATE 1 — oracle symbolic accuracy per sub-task** + oracle caption BLEU-4 (the M8 decision) |
| **3** | Train M1 candidates (dual-encoder U-Net, early-fusion baseline, SegFormer-B0) on one harness. Measure downstream symbolic accuracy on predicted maps. Router + stubbed backend. | **GATE 2 — mIoU @L3/19/coarse-7 and TRANSFER factor per sub-task** |
| **4** | **The A1 falsification ablation** (blind / majority / VLM-only / symbolic-only / hybrid / oracle). M3, M4, M5. Emergency RGB-only VLM adapter. | **GATE 3 — the falsification test.** If symbolic loses on the computable sub-tasks, fall back to the VLM path **now**, with four weeks left |
| **5** | M6 + CDVQA conversion. **Re-fit M2's parameters on predicted maps.** M9 calibrator. Frontend against real endpoints. | CDVQA accuracy + question-only blind baseline; ECE + risk–coverage curve |
| **6** | M7 adapter. M8 if gated in. **BHARAT-VAL evaluation.** Indian adaptation stages 1–2. | **GATE 4 — European and Indian numbers side by side in one table** |
| **7** | Full ablation suite. Perturbation table (8 rows). Bootstrap CIs + McNemar tests. Error analysis. PDF report. | The complete results tables, in the paper's layout |
| **8** | **Freeze.** No new features. Rehearse. Write the honest-limitations slide. | Nothing new is built |

### 6.2 Why the geometry engine and the oracle come *before* training M1

This is the single most important ordering decision in the plan, and it inverts the reflex ("train the model first").

**Reason 1 — the oracle is the ceiling of the entire strategy, and it costs zero GPU hours.**
`ORACLE(t)` is symbolic accuracy computed on *ground-truth* maps. It requires no trained model at all [REV §6.12]. It answers the question that decides whether the project is viable: *if segmentation were perfect, would this approach work?* Training M1 first would produce a number that conflates two unknowns — "is the idea right?" and "is the segmentation good enough?" — and you could not tell which was binding.

**Reason 2 — a low oracle means the fix is not a model.**
If `ORACLE(t)` is low, the answer grammar has not been recovered: the connectivity convention, the MMU, the dilation radius or the hierarchy aggregation is wrong. That is fixed by mining the parquet, **not** by training [REV §6.12]. Discovering this in week 6, after four weeks of GPU time, would be fatal to an 8-week project.

**Reason 3 — M2's parameters must be fitted on clean maps first.**
Connectivity, MMU and dilation radius are recovered by sweeping settings against *ground-truth* maps until the released annotations are reproduced exactly [REV §3.2]. You cannot fit a convention and a segmentation error simultaneously — the fit would absorb the model's noise. They are re-fitted against *predicted* maps in week 5, once M1's error characteristics are known and separable.

**Reason 4 — the dependency order forces it anyway.**
M3 and M4 must be trained on features computed from **predicted** maps so they learn to compensate for M1's systematic biases [REV F3]. So M1 must exist before M3/M4. And M2 must exist before either, because it produces their input features. The chain `M2 → M1 → M3/M4 → M9` is a hard dependency order.

**Reason 5 — it front-loads falsification.**
Weeks 2 and 4 are both designed to be able to kill the plan while there is still time to execute the fallback. [REV §6.13] calls this "a staged bet with a real exit, not a gamble", and notes that stating the exit condition in advance is itself a credibility signal.

### 6.3 What must never be cut

[REV §7.4]: the symbolic path, the evaluation harness, the execution trace, input validation, the oracle experiment, BHARAT-VAL, and the mandatory capabilities.

### 6.4 What was deliberately cut from Architecture A

Cross-modal fusion attribution as a runtime service (kept as an *experiment*); the caption stylizer unless week-2 gates it in; LEVIR-CD/CC; LoveDA; NISAR; the 0.5B LLM query-classification fallback (replaced by M10); test-time adaptation (implement, default OFF); multi-scale training (replaced by scale-consistency augmentation); frontend polish beyond map + overlay + trace panel + evidence panel.

---

## 7. Testing plan

Per [CM §9]: unit + integration + e2e are required; Pydantic validates at boundaries; production logic lives in `src/`, never in notebooks. Synthetic fixtures must be labelled `SYNTHETIC` in filename and docstring [CM §7].

### 7.1 Per-component

| Component | Unit | Integration | Data | Model | Pipeline | Edge case |
|---|---|---|---|---|---|---|
| **V1** | Each check in isolation (bands, dtype, CRS, geotransform, shape, NoData) | V1 → P1 manifest contract | Malformed/truncated GeoTIFF corpus | — | Rejection path returns a typed error, never a crash | 0-band file; 1-band file; mismatched CRS pair; non-co-registered pair; 8-bit vs 16-bit; NaN NoData; **adversarial metadata string** |
| **P1** | dB conversion; bilinear 20→10 m; z-score with frozen statistics | P1 → M1 tensor shape/dtype | **Leakage test: statistics must come from train split only** | — | Band-presence mask propagates correctly | All-zero band; missing band; single-image inference (no batch statistics available) |
| **Q1** | Each template rule; CLC synonym resolution at L1/L2/L3 | Q1 → R1 typed tuple | — | — | Rule failure → M10 handoff | Empty query; 10k-char query; control characters; **prompt-injection string**; synonym ambiguous across levels |
| **M10** | Vectoriser + SVM fit/predict | Q1 fallback path | Train/test split of paraphrased queries | **Accuracy ≥98%** on held-out human paraphrases | — | Out-of-vocabulary query; below-threshold → clarification, not a guess |
| **R1** | Registry lookup per (intent × input_config) | Full plan execution | — | — | Every registered intent produces a valid plan | Unknown intent; 1 image for a change query; 2 images for a single-image query; **parameter out of Pydantic bounds** |
| **M1** | Forward-pass shapes; loss terms individually; TTA averaging | M1 → M2 map contract | Label integrity; `ignore_index` honoured; class distribution | **Smoke test: overfit 10 batches** [CM §4]; then per-class IoU | Cache key = `hash(bytes)+model_version` | All-one-class patch; unclassified-heavy patch; dropped modality; dropped bands |
| **M2** | **Property-based (Hypothesis)** on synthetic maps with known component structure; **golden-file suite** | M2 → M3/M4/M7 typed structs | Fitted parameters reproduce released annotations | **Oracle exact-match ≥99%** on presence/area/adjacency/rel-pos | Aggregation → mask → cleanup → components → props | Single-pixel component; component touching all four borders; checkerboard; empty mask; component exactly at the MMU threshold; **two regions joined by a 1-pixel bridge** |
| **M3** | Feature construction | M2 → M3 → M9 | Class balance matches the benchmark's balanced options | Per-subtype accuracy, AUC, **ECE**; McNemar vs fixed threshold | — | computed=0; stated=0; log-ratio at ±∞ |
| **M4** | Option parsing; fitted distance metric | M5 → M4 for metadata path | Distractor spacing quantified from the parquet | Per-sub-task accuracy; **instruction-following = 100% by construction** | — | Tied options; unparseable option; option out of the computed range |
| **M5** | 12-ch stem; 3 heads | M5 → M4 | Köppen lookup correctness against the 1 km raster | Top-1 per attribute + derived 4-option MCQ accuracy | — | Patch straddling a country border; a season boundary date |
| **M6** | Siamese weight sharing (**assert the two encoders are the same object**); each loss term | M6 → T → M2 | SECOND split integrity | SECOND mIoU/SeK/F1; **CDVQA + mandatory blind baseline** | Transition matrix coherence | No change at all; total change; T1 == T2; 2-px shifted T2 |
| **M7** | Constrained decoding: yes/no logit comparison, length-normalised MCQ log-likelihood, grammar-constrained boxes | M2 attribute struct → M7 (**assert: JSON in, never a sentence**) | Subsample fraction recorded | BLEU-4/ROUGE/METEOR/CIDEr/BERTScore + instruction-following | Fallback rung firing rate | Empty attribute struct; **assert M7 never emits a scored number** |
| **M8** | Seq2seq round-trip | M2 → template → M8 | Aligned (template, released) pairs | BLEU-4 etc. **+ automated factuality check: re-extracted attributes must match the source struct** | — | Caption with 0 classes; with all 44 |
| **M9** | Feature extraction | All heads → M9 | Calibration split used for **nothing else** | **ECE, Brier, reliability diagram, risk–coverage** | Both abstention modes | All-features-missing; P(correct) at exactly τ |
| **A1** | Template substitution | Full e2e | — | — | Trace is append-only and complete | **Assert: no number in the output originates outside M2** |

### 7.2 Cross-cutting test suites

**Data tests** [CM §7]: target leakage; train/test contamination; duplicate and near-duplicate leakage (perceptual hash across the corpus); **geographic leakage** (assert no 1° grid cell spans a split boundary); preprocessing leakage (assert normalisation statistics derive from train only).

**The benchmark quarantine test** [CM §7]: a loader guard that **raises** unless `ALLOW_BENCHMARK_EVAL=1`. Test that it raises by default, and that no training or tuning code path can set it.

**Regression tests**: golden files for M2 on a fixed synthetic map set; a frozen small evaluation slice re-run on every commit; the seed-determinism test (same seed ⇒ identical outputs) [CM §8]; assert every saved model records weight hash, config hash, git commit, dataset version and seed.

**Pipeline / e2e**: one test per query family from §3 — GeoTIFF + question in, JSON + evidence + trace out. Assert the firing matrix: e.g. for a metadata MCQ, **assert M2 was never invoked**; for adjacency, **assert M7 was never invoked**.

**API tests**: schema validation on every response; typed rejection on malformed input; the trace is complete and append-only.

**Security tests**: prompt injection via the query string; prompt injection via **GeoTIFF metadata strings** (this path reaches Q1/M10 [REV §3.10]); assert no `eval()` and no dynamic import exists in the routing path; Pydantic bounds enforcement on every tool parameter.

---

## 8. Accuracy improvement plan

### 8.1 The functional form — this replaces targets

[REV §6.12] refuses to state a target accuracy and gives the *form* the target must take instead. `CLAUDE.md` §11 makes this binding: never set an arbitrary target before the measurement exists.

```
For each sub-task t:

    TARGET(t)  =  ORACLE(t)  ×  TRANSFER(t)

    ORACLE(t)   = symbolic accuracy on GROUND-TRUTH maps.
                  Measured week 2. Requires no trained model. Zero GPU hours.
                  This is the ceiling of the entire strategy.

    TRANSFER(t) = predicted-map accuracy ÷ ground-truth-map accuracy,
                  measured on the first segmentation checkpoint. Week 3.

    If ORACLE(t) is low   → the answer grammar is not recovered.
                            Fix the parquet mining. NOT a model problem.
    If TRANSFER(t) is low → segmentation quality is binding.
                            Spend the effort on M1.
```

This is the honest version of "our target is 85%". It has the property that when a judge asks *how do you know?*, the answer contains two measurements.

### 8.2 Improvement levers, routed by which factor is binding

**If `ORACLE(t)` is binding** — the conventions are wrong, and no GPU time helps:
- Re-fit connectivity (4 vs 8), MMU, opening kernel, adjacency dilation radius against released annotations until reproduced exactly.
- Fix the hierarchy aggregation table (the F1 error class).
- Re-mine the parquet for the tolerance band and distractor spacing.

**If `TRANSFER(t)` is binding** — segmentation is the constraint:
- Loss composition: `L_CE + 0.5·L_Lovász + 0.3·L_hier + 0.2·L_scale` — the hierarchy term specifically targets **sibling confusion**, which is what the benchmark's adversarial "no" answers exploit (VERIFIED). Optimise against the off-diagonal mass *inside* the sibling boxes, not against overall accuracy.
- Class balancing: inverse-**sqrt** frequency weighting **capped at 5×** (full inverse-frequency at 44 classes destabilises training); Lovász auxiliary; stratified oversampling of tail classes at a modest 2–3×; **always report per-class IoU**.
- 8× TTA (4 rotations × 2 flips), logits averaged — reliably worth a point or two and it does **double duty** as M9's strongest confidence feature.
- SWA / last-k checkpoint averaging — one run, no extra inference cost.
- 2–3 model ensemble (U-Net + SegFormer-B0) — **only if week 7 has slack**; it costs the one-GPU deployment story.
- Re-fit M2's cleanup parameters on **predicted** maps (week 5): the optimal cleanup for a noisy map is not the optimal cleanup for a clean one. Architecture A did the first fit and not the second.
- Train M3/M4 on **predicted-map** features so they absorb M1's systematic bias — if the segmenter over-fragments forest, M3 learns the counts run high and shifts the boundary. Free accuracy, invisible to anyone treating tolerance as a constant.

**Hyperparameter policy** [REV §6.6]: **do not run a large sweep.** Fix by convention what the reference recipe fixes. Tune only three things for M1, sequentially, one axis at a time — learning rate (3 log-spaced values), loss weights (2–3 combinations), augmentation strength (on/off/heavy). **~8 runs total.**

### 8.3 Evaluation integrity — the non-negotiables

1. **The benchmark split is quarantined.** 1,082 pairs / 15,029 annotations, touched once, at the end, behind the `ALLOW_BENCHMARK_EVAL=1` guard. Tuning on it is lying to yourself and the number will not survive the hidden set.
2. **Geographic block CV, k=5** [CM §1]. Random k-fold places near-identical patches on both sides and inflates validation mIoU by several points; you then make architecture decisions with a biased instrument.
3. **Blind baselines are mandatory** [REV F8]: question-only, majority-class per sub-category, and class-prior. If the system does not clearly beat these, the benchmark is measuring priors, not perception — and that must be reported.
4. **The significance floor.** Given the split sizes (~1,700 binary annotations and ~700 MCQ annotations per sub-task): 95% CI ≈ **±2.2 points** at p≈0.7 for binary, **±3.7 points** at p≈0.5 for MCQ. Therefore: **do not claim a difference under ~3 points on a binary sub-task or ~4 points on an MCQ sub-task.** State this rule explicitly in the report. Do not hill-climb on differences that small — you would be fitting noise.
5. **Bootstrap CIs resample over the 1,082 image pairs, not over annotations.** Annotations within a pair are correlated; resampling them independently produces intervals that are too narrow.
6. **McNemar's test** for every paired comparison — both systems answer identical items, so McNemar is correct and far more powerful than comparing independent proportions.
7. **Every fitted preprocessing parameter is fitted on training data only** [CM §7] — normalisation statistics, class weights, TF-IDF vocabulary, scalers, MMU/dilation/connectivity.
8. **Report both domains in every table.** European mIoU and Indian coarse-7 mIoU side by side, in every experiment row. "The moment you allow a European-only number into a slide, you have started deceiving yourself" [REV §5.6].
9. **Record predictions in advance.** [REV §6.12] lists falsifiable PRIORs about the *shape* of results (area strongest, counting weakest, MCQ capped by the metadata sub-tasks, captioning highest-variance). Check them in week 7 and **report both the hits and the misses**.
10. **Matched-compute comparison.** Report GPU-hours for both paths. "We match a per-task fine-tuned VLM at ~1/N of the training compute" is a stronger and more defensible claim than raw accuracy.

### 8.4 The falsification experiment (Gate 3)

Six configurations, scored **per sub-category, on identical questions** [REV §6.13]:

| Config | Method | What its row tells you |
|---|---|---|
| **Blind** | Question text only, no image | If close to our system, the benchmark measures language priors, not perception |
| **Majority** | Most frequent answer per sub-category | The floor |
| **VLM only** | Fine-tuned M7 answers everything | The published-baseline path |
| **Symbolic only** | Geometry engine answers everything computable | The bet |
| **Hybrid (ours)** | Router: computable → symbolic, generative → VLM | Whether the router earns its complexity |
| **Oracle** | Geometry engine on **ground-truth** maps | Separates "the idea is wrong" from "the segmentation is imperfect" — the most valuable row, and one nobody else will have |

**The falsification condition, stated in advance:** *a predicted LULC map plus deterministic geometry will beat a fine-tuned VLM on counting, area, adjacency, relative position and referring expressions, at a fraction of the training compute.* If it fails in week 4, fall back to the VLM path with four weeks left.

---

## 9. Risk register

Likelihood and impact are my assessment (DERIVED) unless the documents rank them; the risks themselves are from [REV F1–F12, §5, §7] and [PDF §117, §121–122].

### 9.1 Technical

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| Hierarchy aggregation not implemented or wrong (the F1 error) | Med | **Critical** | Counting oracle accuracy is low while presence/area oracle is high | Taxonomy YAML as a first-class object, built day one; aggregation is M2 step 0 and runs **before** connected components; golden-file tests |
| Wrong connectivity / MMU convention | **High** | High | Oracle count accuracy < 99% while area accuracy ≈ 100% | Exhaustive sweep against released counts in week 2; re-fit on predicted maps in week 5 |
| GeoTIFF loaded with PIL/OpenCV somewhere in the codebase | Med | **Critical** | Areas wrong by a constant factor; CRS missing from the manifest | `rasterio` only [CM §1]; V1 asserts geotransform present; a lint/grep test banning `PIL`/`cv2`/`imread` in `src/` |
| Normalisation statistics leak (per-image or per-batch) | Med | High | Validation mIoU good, single-image inference bad | Frozen, versioned, hashed statistics file; explicit leakage test |
| Counting is the weakest sub-task and stays weak | **High** | Med | Count TRANSFER factor far below area's | Predicted-map re-fit of opening/MMU; count-error decomposition (over- vs under-count have **opposite** fixes: opening vs closing) |
| M6's three heads disagree → incoherent transition matrix | Med | High | Change mask contradicts `argmax(map_t1) ≠ argmax(map_t2)` | The `0.3·consistency` loss term is mandatory; assert coherence in tests |
| Mixup/CutMix silently introduced by a well-meaning team member | Med | High | Counting accuracy drops with no other explanation | Explicitly forbidden [CM §1]; add to the augmentation config schema as a rejected key |

### 9.2 Data

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| **Geographic leakage** in the internal validation split | **High** | High | Validation mIoU implausibly high; small train/val gap | Block by country / 1° grid / S2 tile ID; assert no cell spans a boundary |
| Benchmark split contaminated by tuning | Med | **Critical** | Any code path reads it before final evaluation | `ALLOW_BENCHMARK_EVAL=1` loader guard; test that it raises by default |
| Answer grammar not recovered from the parquet | Med | **Critical** | Oracle accuracy low across **all** sub-tasks | Week 1 is dedicated to this; `ANSWER_GRAMMAR.md` is the week-1 gate |
| Licence status of SECOND / CDVQA / VRSBench / reBEN checkpoints unresolved | Med | High | No licence table exists by end of week 1 | Week-1 licence audit; a table, not a hesitation |
| reBEN pretrained checkpoints were trained on train+val+test → leakage | Low | High | — | Check the model cards in week 1 (open question #9) |
| WorldCover/Dynamic World label noise poisons Indian adaptation | **High** | Med | Indian fine-tuning degrades European mIoU without improving Indian | Confidence-weighted pseudo-labels; train on inter-source **agreeing** pixels; tag weak labels in the dataset index and never average them into a headline number |
| Near-duplicate patches across the internal split | Med | Med | — | Perceptual hash across the corpus |

### 9.3 Model

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| L3-44 mIoU is very low and drags everything | Med | High | **If L3 mIoU < ~25, something is wrong with the label loading, not the model** [REV §3.1] | Check the loader first; report mIoU at L3/19/coarse-7 and per-class always |
| M8 gate lands in the "drop symbolic captioning" band (<10 BLEU-4) | Med | Med | Week-2 oracle caption score | Route captioning to M7; the gate is designed to make this a cheap decision |
| M5 turns out unnecessary (harness supplies metadata) | Med | Low | Week-1 parquet inspection | Discard the model — this is a *good* outcome, not a loss |
| Over-adapting to India destroys European performance | Med | High | European mIoU drops > ~2 points | **The replay-and-stop rule**: interleave European batches at 20–30%; back off if European mIoU drops >2 points |
| Not reproducing the published 34.04 BLEU-4 | **High** | Low | — | **Say so up front.** Compare against InternVL3-1B **zero-shot** (0.45 BLEU-4, 54.11 binary, 26.76 MCQ, 5.76 ref-exp), which is the fair and winnable comparison; report the subsample fraction honestly |

### 9.4 Security

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| Prompt injection via **GeoTIFF metadata strings** reaching Q1/M10 | Med | Med | — | V1 sanitises metadata strings; Q1/M10 strip control characters and cap length |
| Prompt injection via the query string | Med | Low | — | Closed intent vocabulary; M10 is a linear SVM with no generative surface |
| Arbitrary execution via a dynamic tool path | Low | **Critical** | — | **No `eval()`, no dynamic plugin loading, no LLM planner** [CM §1]; frozen registry; Pydantic bounds |
| Malformed/hostile GeoTIFF crashes the service | Med | Med | Untyped exception escapes V1 | V1 returns a typed rejection; fuzz corpus of malformed rasters |

### 9.5 Integration

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| A component consumes another's natural language | Med | High | A sentence appears in an inter-component payload | Typed structures at every boundary; e2e test asserting M7 receives JSON, never a sentence |
| A number is parsed back out of generated text | Low | **Critical** | — | The number-flow rule [CM §2]; A1 asserts provenance |
| Scene cache serves a map from a different checkpoint | Low | High | Irreproducible results between runs | Cache key = `hash(scene_bytes) + model_version` |
| M6's input format (RGB 512×512) vs the deployment input (S1+S2 GeoTIFF pair) | **High** | High | The change path cannot run on a real hidden-set input | **Unresolved — see §10.2.** Needs a design decision |

### 9.6 Performance

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| Cannot fit segmenter + VLM on one 24 GB GPU | Low | Med | OOM in week 6 | Architecture B is sized for one 24 GB GPU "comfortably"; M7 is 1.1B with 5.8M trainable |
| 8× TTA makes inference too slow for a live demo | Med | Low | Per-query latency in the trace | Scene cache means the map is computed **once** per scene and serves unlimited queries |
| GPU not secured by end of week 1 | Low | **Critical** | — | **This is the documented trigger to build Architecture C instead** [REV §7.3] |

### 9.7 Delivery & demonstration

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| **Scope overrun — arriving at week 7 with six half-built components and no measured numbers** | **High** | **Critical** | Any week's Friday gate number does not exist | [REV F9] names this **the single highest-probability failure mode of the project** — above any architectural error. Architecture B is deliberately smaller than A; week 8 is a hard freeze; §6.4 lists what was cut |
| Uncontrolled feature development | **High** | High | New features appearing after week 6 | [PDF §117] names this one of the largest project risks. Week 8: nothing new is built |
| Fewer than 4 of 6 members can commit substantial time | Med | **Critical** | — | **Documented trigger to build Architecture C.** "Do not build a half-finished B. A complete simple system beats an incomplete sophisticated one, every time, in front of judges who can only evaluate what runs" [REV §7.3] |
| A mixed-provenance number appears on a slide | Med | Med | A table cell without a source | Fix the provenance of **every** cell — [REV §0.1E] notes the previous document mixed three tables into one row, and "if you put that in front of the authors' colleagues at SAC, someone will notice" |
| Claiming a Cartosat/RISAT number | Low | **Critical** | Any Indian-sensor accuracy figure appears | **Never.** Report the four-axis gap table and the perturbation suite instead. A SAC judge will know the difference immediately |
| Demo fails live | Med | High | — | Week 8 is rehearsal only; scene cache makes repeat queries fast; abstention in operational mode names the failing class rather than guessing |

---

## 10. Assumptions & ambiguities

This section drives Stage 3. Items in §10.1 are the architecture's own open questions; §10.2 are ambiguities I identified while reading and which are **not** resolved by either document.

### 10.1 The architecture's own open questions [REV Appendix B]

| # | Question | Why decision-critical | Resolve by |
|---|---|---|---|
| 1 | At which CLC level do the benchmark's questions name classes — L1, L2, L3, or mixed? | Determines the segmentation target and the aggregation table. **The single highest-impact unknown.** | Week 1, from the parquet |
| 2 | What metadata rides along with each annotation (season, country, climate zone, geolocation)? | Decides whether M5 is a model, a lookup, or a discard | Week 1, from the parquet |
| 3 | Connectivity convention: 4 or 8? | Swings **every** counting answer | Week 2, by fitting against released counts |
| 4 | Distractor spacing for MCQ area and count | Tells you precisely how accurate M1 must be — a design input, not a post-hoc observation | Week 1, from the parquet |
| 5 | Tolerance band for binary area/count "yes" | Determines M3's feature design | Week 2 |
| 6 | Does "or the any open source training data" in the problem statement permit corpora beyond BigEarthNet.txt? | **If denied, the change path is impossible** — BigEarthNet.txt is single-timestamp, so some external corpus must be permitted. Ask in writing | Idea round |
| 7 | Does the ISRO/SAC hidden set exercise all five capabilities, or focus on the cross-modal pair? | If cross-modal is central it deserves more investment than its benchmark weight implies | Idea round |
| 8 | Licence status of SECOND, CDVQA, VRSBench, and the reBEN pretrained checkpoints | "Are your training data legally usable?" should get a table, not a hesitation | Week 1 |
| 9 | Were the reBEN pretrained checkpoints trained on train only, or train+val+test? | If the latter, using them leaks into the evaluation | Week 1, from the model cards |
| 10 | Is Bhoonidhi data at ≥5 m genuinely open for a non-government entity under current policy? | A policy claim made on stage in front of SAC judges must be right | Week 1 — verify directly, do not repeat a second-hand claim |

### 10.2 Ambiguities identified in this reading

**A1 — The "five mandatory capabilities" are never enumerated.**
Both documents reference them — [REV §7.2] scores "compliance with the five mandatory clauses", [REV §7.4] says never cut "any of the five mandatory capabilities", [PDF §113] repeats it — but **neither document lists them**. This directly blocks §11 (Definition of Done): we cannot assert compliance with an unenumerated list.
**ASSUMPTION — REQUIRES VALIDATION.** Source: the SIH26167 problem statement. **Owner: human. Needed before Stage 3.**

**A2 — The `S1..S23+` stage numbering in `CLAUDE.md` §11 does not exist in either architecture document.**
`CLAUDE.md` §11 anchors the four gates at S8, S13, S16, S23. Both architecture documents use an **8-week** plan. The gates map cleanly onto weeks:

| Gate | CLAUDE.md stage | Architecture week | Number |
|---|---|---|---|
| GATE 1 | S8 | Week 2 | Oracle symbolic accuracy |
| GATE 2 | S13 | Week 3 | Transfer factor |
| GATE 3 | S16 | Week 4 | A1 falsification |
| GATE 4 | S23 | Week 6 | BHARAT-VAL coarse-7 mIoU |

But the **full S1–S23+ decomposition is not specified anywhere in the repo.** I have not invented one. **UNKNOWN — human decision required before Stage 2.**

**A3 — Naming collision: "A1".**
Used for the **Answer Assembler** [PDF §78] and for the **falsification ablation experiment** [REV §6.13, PDF §117 week 4]. `CLAUDE.md` §11 GATE 3 says "A1 falsification", i.e. the experiment. Proposal: rename the assembler `ASM` in code, keep `A1` for the experiment. **Needs a decision.**

**A4 — Naming collision: "S1".**
Used for **Sentinel-1** throughout, and for the **geometry engine** in [REV §2.2]'s stage-6 diagram. The PDF resolves this by calling the geometry engine **M2** consistently, and `CLAUDE.md` §1 also uses M2. **Resolution: `S1` = Sentinel-1 only; the geometry engine is `M2`.** Recorded here so the review's diagram does not mislead.

**A5 — Query family count: "seven" vs nine.**
The Stage-1 prompt says seven families and lists nine. M10 performs **8-way** intent classification [PDF §13]. BigEarthNet.txt spans **15 tasks** [REV §4.2]. Three different counts (8 / 9 / 15) for what appear to be overlapping vocabularies, and **none of them is enumerated** in either document. Resolving this is a prerequisite for R1's registry and M10's label set.
**UNKNOWN — resolve in week 1 from the parquet** (it is the same investigation as open question #1).

**A6 — Does area exclude MMU-dropped components?**
[REV §2.2] presents M2's steps 0–5 as one sequence, with `area = Σ pixels × GSD²`. Whether the sum runs over the *cleaned, MMU-filtered* mask or the *raw* aggregated mask is not stated. It changes every area answer. **ASSUMPTION — REQUIRES VALIDATION.** Resolvable empirically in week 2 by fitting both variants against released area annotations.

**A7 — Is M5 wired into the caption path?**
Season, country and Köppen zone are appended during *reference* caption generation from external maps (VERIFIED, [REV F4]). Neither document says whether our caption attribute struct should include M5's posteriors. If the reference captions contain those attributes and ours do not, we lose n-gram overlap for free.
**ASSUMPTION — REQUIRES VALIDATION** in week 2 against released captions.

**A8 — M6's input format vs the deployment input format.**
M6 is specified on **SECOND: bi-temporal aerial RGB, 512×512, 0.5–3 m GSD, Chinese cities** [REV §3.6]. The deployment and hidden-set input is a **co-registered optical + SAR GeoTIFF pair over India**. Neither document specifies the bridge — whether M6 takes an RGB view of the S2 bands, whether it is resized, whether it runs at 120×120 at all, or whether the change path is RGB-only by design. This is a **high-likelihood, high-impact integration gap** (§9.5). **UNKNOWN — human decision required.**

**A9 — Does M3/M4 fire on the change path?**
[PDF §129] shows `M6 → transition matrix → M2 → M3/M4 → M9`, so yes. But CDVQA's answers are a **closed set of 19 categories** [REV §4.2], which is a 19-way classification, not a binary decision or a 4-option MCQ. How M3/M4 map onto a 19-way closed set is unspecified. **ASSUMPTION — REQUIRES VALIDATION.**

**A10 — The M1→India stop rule threshold.**
"Back off if European mIoU drops by more than ~2 points" [REV §5.5]. The `~` is doing real work, and the significance floor (§8.3) says differences under ~3 points on a binary sub-task are not distinguishable from noise on the benchmark split. The stop rule is stated on mIoU, not on sub-task accuracy, so these are not directly comparable — but the threshold needs to be made exact before week 6. **ASSUMPTION — REQUIRES VALIDATION.**

**A11 — Köppen zone class count `k`.**
"k determined by what appears in reBEN" [REV §3.5]. Not yet known. **UNKNOWN — week 1, from the metadata.**

**A12 — Which PDF is canonical.**
`CLAUDE.md` §0 names `docs/architecture/SatQuery_Architecture.pdf`. The repo file is `SatQuery_Architecture (1) (1).pdf` (browser-duplicated filename). Content-wise it **is** Architecture B and it is consistent with `CLAUDE.md` §1's frozen facts. Recommend renaming it to the canonical filename so §0 resolves. **Minor — but it should be fixed before anyone else clones the repo.**

### 10.3 Unvalidated performance expectations (PRIORs — not targets)

Recorded so week 7 can check them, per [REV §6.12]'s instruction to write predictions down in advance:

- Area will be the **strongest** symbolic sub-task; **counting the weakest** — the reverse of Architecture A's assumption.
- Presence will be bounded by CLC **sibling confusion**, not by method.
- Referring **point** detection should be near-trivial; referring expression should be strong.
- Captioning is the **highest-variance** outcome; the week-2 gate decides it.
- MCQ overall is **capped** by the three metadata sub-tasks, which no geometry can solve.
- M1 L3-44 mIoU PRIOR range 30–50, coarse-7 75–88 — **moderate confidence, dragged down by the long tail. Measure in week 3 and replace the table.**

**None of these are targets.** [CM §11]: never set an arbitrary target before the measurement exists.

---

## 11. Definition of done

SatQuery is SIH-ready when **all** of the following hold. Nothing here is an accuracy threshold — per [CM §11], the gates report numbers and a human decides.

### 11.1 Measurement completeness

- [ ] **GATE 1** measured and reported: oracle symbolic accuracy per sub-task, on ground-truth maps.
- [ ] **GATE 2** measured and reported: transfer factor per sub-task = predicted ÷ oracle.
- [ ] **GATE 3** measured and reported: the six-config A1 falsification table, per sub-category, on identical questions.
- [ ] **GATE 4** measured and reported: BHARAT-VAL coarse-7 mIoU, **next to** the European number.
- [ ] Each gate was reported to a human and a decision was recorded [CM §11].
- [ ] `TARGET(t) = ORACLE(t) × TRANSFER(t)` is populated for every sub-task from real measurements.

### 11.2 Evaluation integrity

- [ ] The benchmark split was touched **exactly once**, at final evaluation, behind the `ALLOW_BENCHMARK_EVAL=1` guard.
- [ ] Blind (question-only), majority-class and class-prior baselines reported for every sub-category.
- [ ] CDVQA question-only blind baseline reported (mandatory — documented language bias).
- [ ] Bootstrap CIs on every headline number, resampled over the **1,082 pairs**.
- [ ] McNemar's test on every paired comparison.
- [ ] The significance floor (~3 pts binary / ~4 pts MCQ) stated explicitly in the report, and no claim violates it.
- [ ] Geographic block CV (k=5) used for all decision-making; fold variance reported.
- [ ] Leakage tests pass: target, contamination, duplicate, geographic, preprocessing.
- [ ] Every table cell's provenance is correct and single-source.

### 11.3 Architectural compliance

- [ ] The number-flow rule holds everywhere: no scored number originates outside M2. Asserted in tests, not just documented.
- [ ] No component consumes another component's natural language.
- [ ] Routing is deterministic: no LLM planner, no `eval()`, no dynamic plugin loading; all parameters Pydantic-validated.
- [ ] `rasterio` only for GeoTIFFs — enforced by a test, not a convention.
- [ ] No Mixup/CutMix anywhere in the augmentation path.
- [ ] Zero architecture deviations in `PROJECT_STATUS.md`, or each one carries an approved `=== PROPOSED ARCHITECTURE CHANGE ===` record [CM §6].

### 11.4 Reproducibility

- [ ] Global seed set for `random`/`numpy`/`torch`/CUDA and recorded in every result artifact.
- [ ] Every saved model records weight hash, config hash, git commit, dataset version, seed.
- [ ] All parameters in `configs/*.yaml`; no magic numbers in `src/`.
- [ ] `make reproduce` rebuilds the pipeline from a clean environment.
- [ ] A dataset card exists in `docs/datasets/` for every dataset used.
- [ ] Normalisation statistics are frozen, versioned and hashed into the model card.

### 11.5 System completeness

- [ ] All nine stages implemented; all nine query families run end-to-end.
- [ ] Every query family has a passing e2e test asserting the **firing matrix** (§3.1).
- [ ] Both abstention modes work; the fallback-rung firing rate is measured and reported.
- [ ] Structured JSON, evidence overlay, append-only execution trace and PDF report all produced.
- [ ] Runs locally on one GPU.
- [ ] Security tests pass, including prompt injection via GeoTIFF metadata strings.

### 11.6 Honesty

- [ ] **No Cartosat/RISAT accuracy number is claimed anywhere.**
- [ ] The four-axis Indian gap table (spectral / spatial / SAR / geographic) is presented with the three simulable axes measured and the sensor axis stated as unmeasurable.
- [ ] The 8-row perturbation table is published **in full, including the rows where we lose**.
- [ ] The honest-limitations slide exists: M1 quality is the ceiling; the Indian sensor gap is unmeasured; 34.04 BLEU-4 was not reproduced and why.
- [ ] The week-7 check of §10.3's advance predictions reports **both the hits and the misses**.
- [ ] The M7 training subsample fraction is reported.
- [ ] Every performance claim is labelled PUBLISHED, measured, or PRIOR — never presented as fact when it is an expectation.

### 11.7 Open items blocking "done"

- [ ] §10.2 **A1** — the five mandatory capabilities are enumerated and each is demonstrably met.
- [ ] §10.2 **A2** — the S1–S23+ stage decomposition exists, or `CLAUDE.md` §11 is amended to the week numbering.
- [ ] §10.2 **A8** — M6's input-format bridge to the deployment input is decided and implemented.
- [ ] All ten of [REV Appendix B]'s open questions closed, each with an owner and a recorded answer.

---

## Appendix — Published reference numbers

Transcribed from arXiv:2603.29630 Tables 2–8 via [REV Appendix A] / [PDF §119]. Percentages. **These are the field's numbers, not ours, and not targets.**

| Model | Captioning (BLEU-4) | Binary VQA | MCQ | Ref-exp detection |
|---|---|---|---|---|
| Best evaluated RS-specific model | 1.66 | 58.38 | 35.26 | 16.18 |
| Best evaluated general CV model | 0.96 | 61.96 | 37.55 | 31.73 |
| **InternVL3-1B, zero-shot** | **0.45** | **54.11** | **26.76** | **5.76** |
| RS-InternVL (fine-tuned reference) | 34.04 | 73.29 | 51.49 | 65.84 |

Binary VQA sub-tasks — the ones the symbolic path targets:

| Model | Presence | Area | Count | Adjacency |
|---|---|---|---|---|
| Best evaluated RS model (EarthMind, RGB) | 69.34 | 56.20 | 51.07 | 55.97 |
| Frontier general model (reported ~2T params) | 61.59 | 67.38 | 61.94 | **55.86** |
| Qwen3-VL-8B | 64.33 | 66.62 | 62.33 | 58.45 |

**Caveats that must accompany these numbers** [REV Appendix A]:
- The RS-InternVL row is **not one model** — it is four-plus separately fine-tuned per-task adapters, trained on train+val combined for one epoch at ~2 days on 4× H200. Anyone claiming to beat it with a single unified model is comparing unlike things.
- Because they trained on train+val, **no clean held-out validation set remains** in the published setup. Carve our own from train, by geographic block.
- Answers were extracted even when models violated the output format, so the published numbers are already **generous to the weaker models**.

**The InternVL3-1B zero-shot row is the fair, winnable comparison** for M7 — not the 34.04.

---

*This document records comprehension only. No code has been written, no metric measured, no dataset downloaded. Every ASSUMPTION and UNKNOWN above is unresolved as of 2026-08-29.*
