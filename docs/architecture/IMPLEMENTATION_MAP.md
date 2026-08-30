# SatQuery — Implementation Map

**Status:** **Stage S0** deliverable — architecture comprehension. No code written, no metric measured, no dataset downloaded.
**Date:** 2026-08-29
**Stage numbering:** **S0–S26**, our own execution breakdown, defined in `STAGE_PROMPTS.md`. This is *not* the architecture document's numbering — the PDF has only an 8-week plan. The two reconcile via `STAGE_PROMPTS.md` Appendix B and `CLAUDE.md` §11.

### Sources

| Source | Status |
|---|---|
| `docs/architecture/SatQuery_Architecture (1) (1).pdf` — 28 pp., 133 numbered points. **This is Architecture B** and already incorporates the review's corrections (its §2.1 is "The Biggest Correction: 19 Classes vs. 44 Classes"). | Read in full. Cited as **[PDF §n]** |
| `docs/architecture/SatQuery_Architecture_Review_v2 (2).md` — 1,622 lines. The critical review of the *previous* architecture (Architecture A, `SatQuery_AI_Architecture.pdf`) that produced Architecture B. Holds the detailed per-model specifications the PDF summarises. | Read in full. Cited as **[REV §n]** |
| `CLAUDE.md` — standing project rules. | Read in full. Cited as **[CM §n]** |
| `STAGE_PROMPTS.md` — S0–S26 execution breakdown, Appendix A (reusable mid-stage prompts), Appendix B (S-number ↔ 8-week reconciliation). | **Present and read** (committed at S1, 1,558 lines). Every S-anchor used below is verified against it. See §10.2 A2. |
| SIH26167 problem statement. | **NOT SUPPLIED.** See §10.2 A1. |

### Evidence labels

Inherited from [REV §0], extended with the labels required by [CM §5]:

| Label | Meaning |
|---|---|
| **VERIFIED** | The review author read the primary source and confirmed it. |
| **PUBLISHED** | A number transcribed from a paper table the review author read. |
| **PRIOR** | An engineering expectation. Not measured. Falsifiable. |
| **SPEC** | Stated by the architecture documents as a design decision. |
| **DERIVED** | My inference from the documents — logically forced, but not written down. |
| **PROVISIONAL** | Adopted to unblock work; to be replaced by an empirical result at a named stage. |
| **ASSUMPTION — REQUIRES VALIDATION** | My inference that is *not* forced and could be wrong. |
| **UNKNOWN** | Genuinely unresolved. Named owner and deadline required. |

**No accuracy number in this document is a target.** Every number is either PUBLISHED (with source) or explicitly absent. Per [CM §11], targets do not exist until the gate measurements exist.

### Naming conventions fixed at the S0 gate

- **`A1` is reserved exclusively for the Stage S16 falsification experiment**, matching the architecture document's own usage [PDF §117 week 4; REV §6.13]. It is never a component name.
- The Stage-9 output-assembly component is named **Assembler** — `src/inference/assembler.py`, class `AnswerAssembler`. No letter-number code.
- **`S1` means Sentinel-1 only.** The geometry engine is **M2** everywhere, per [PDF §29] and [CM §1]. ([REV §2.2]'s stage-6 diagram labels it `S1`; that label is not used in this project.)

---

## 1. Complete architecture understanding

### 1.1 What the system does

SatQuery receives one or two GeoTIFFs plus an English question, and returns a structured JSON answer with a confidence score, a visual evidence overlay, and an append-only execution trace [PDF §1, §79].

### 1.2 The nine stages

Both documents describe the same nine-stage pipeline [PDF §6 diagram; REV §2.2]. **These nine stages are the architecture's own pipeline stages and are unrelated to the S0–S26 execution stages.**

| # | Pipeline stage | Component(s) | Nature |
|---|---|---|---|
| 1 | **Validation** | V1 | Deterministic |
| 2 | **Preprocessing** | P1 | Deterministic |
| 3 | **Query understanding** | Q1, M10 (fallback) | Deterministic rules; probabilistic fallback |
| 4 | **Routing** | R1 | Deterministic |
| 5 | **Perception** (the learned layer) | Scene cache, M1, M5, M6 | Probabilistic |
| 6 | **Symbolic computation** | M2 | Deterministic (fitted parameters) |
| 7 | **Answer-format decision** | M3, M4, M7 | Probabilistic |
| 8 | **Confidence** | M9 + abstention policy | Probabilistic → deterministic policy |
| 9 | **Assembly and evidence** | Assembler + four output artifacts | Deterministic |

Stages 1–4 turn an untrusted upload and a free-text string into a validated, typed execution plan. Stage 5 is the only place where a neural network looks at pixels. Stage 6 is where the answer's *number* is produced. Stages 7–8 convert that number into the benchmark's required answer format and attach a calibrated reliability estimate. Stage 9 renders it and records how it was obtained.

### 1.3 The perception / measurement / language separation

[PDF §133] names this the most important conceptual distinction in the project:

```
PERCEPTION    what is in the image?                        M1, M5, M6 (M7 when necessary)
     ↓
MEASUREMENT   what does the image mathematically imply?     M2 — and M2 only
     ↓
DECISION      what answer format does the benchmark want?   M3, M4, M5
     ↓
CONFIDENCE    how much should this be trusted?              M9
     ↓
LANGUAGE      how do I express it?                          M7, M8
```

Two rules make this architecturally load-bearing rather than stylistic:

**Rule 1 — the number-flow rule** [CM §2; PDF §78; REV §2.3]. `Image → M1 → M2 → NUMBER → Assembler`. A language model may *phrase* an answer; it may never *produce the numerical value* in it. Numbers are substituted into templates. Parsing a number back out of generated text is a bug by definition.

**Rule 2 — typed structures only** [REV §2.3]. No model consumes another model's natural language. M7 receives a structured attribute dictionary from M2, never a sentence from another component. The chain `M1 → sentence → M7 → sentence → M3` is explicitly forbidden [CM §2]. Models write into a shared typed scene representation that M2 reads; they are hierarchical, not peer-to-peer.

Together these are what make the execution trace mean anything. If a number could originate in generated text, the trace would record a derivation that did not actually produce the answer.

### 1.4 Why predict a map and calculate, rather than ask a VLM

The central bet, and the justification is **not** a claim about model quality. It is a claim about how the benchmark's ground truth was manufactured.

**The benchmark's own construction is the argument** (VERIFIED, [REV §1.1], from §3.1 of arXiv:2603.29630):

> Captions are built by extracting presence, per-class contiguous-region counts, per-class and per-instance sizes, and pairwise adjacency **directly from the pixel-level reference maps**, with areas rounded to the nearest 1000 m² and classes tiered by coverage (>25% primary, 5–25% secondary, <5% marginal). Binary and MCQ annotations are generated from those same four spatial categories. Referring expressions are generated from instance geometry with explicit area and bbox-fill constraints.

The ground-truth answer to "how much forest is there?" was **not** written by a human looking at an image. It was computed by a program that ran over a CORINE reference map. The answer is a deterministic function of a pixel-level map.

The architectural consequence: **the task is not perception, it is measurement** [REV §1.1]. Reproducing the generator's process — predict the map, then run the same measurement — is structurally aligned with how the target was produced. Asking a generative model to *guess* the output of a deterministic program is strictly harder than *running* that program on a predicted input.

**The published evidence that the field currently gets this wrong** (PUBLISHED, [REV Appendix A], Table 3):

| Model | Adjacency (balanced yes/no) |
|---|---|
| Best evaluated RS-specific model (EarthMind, RGB) | 55.97 |
| Frontier general model (reported ~2T params) | **55.86** |
| Qwen3-VL-8B | 58.45 |

A model with a reported two trillion parameters reaches 55.86% on a yes/no question about whether two land-cover regions touch. `scipy.ndimage.binary_dilation` computes the same relation exactly, in microseconds, given a correct map [PDF §120].

> ### ⚠ REQUIRED FRAMING — do not overstate this comparison
>
> **Adjacency is NOT balanced.** Measured at S3 on train+validation (n = 108,672): the
> `binary`/adjacency prior is **57.1% "no" / 42.9% "yes"** — the only one of the four binary
> sub-tasks that is not 50/50. [REV Appendix A] describes this set as balanced; it is not.
>
> **Consequence:** a majority-class baseline that answers "no" to every adjacency question
> scores **57.1%**, which is *above* the 55.86% frontier-model figure. Any claim of the form
> "we beat a 2T-parameter model on adjacency" is therefore weak — that model does not beat
> answering "no" every time.
>
> **The honest framing is symbolic-vs-majority-baseline, not symbolic-vs-frontier-model.** The
> thesis survives — an exact computation should far exceed 57.1% — but it must be stated
> against the correct reference point.
>
> **Binding on:** §8.3 (blind baselines), §8.4 (the A1 falsification table at S16), the S8 gate
> report, and **S26's judge pack**. Whoever writes S26 must not reproduce the "beats a 2T model"
> phrasing without the majority-baseline number beside it.

The argument to make on stage is explicitly **not** "our smaller network is smarter" [PDF §120]. It is: *we changed the problem formulation. Once perception is separated from deterministic spatial measurement, some tasks no longer require generative reasoning at all.*

### 1.5 The second, stronger argument — Indian adaptability

[REV F7] identifies an argument Architecture A never made, and rates it above the leaderboard argument:

- In a **VLM-only** design, the Indian domain gap is distributed across a model that can only be adapted with Indian image–text pairs. **No such corpus exists.** There is no Indian BigEarthNet.txt. You cannot LoRA your way to India without Indian instruction data.
- In the **segmentation-plus-symbolic** design, the entire Indian gap is concentrated in *one* model — M1 — which can be adapted with Indian pixel labels, which are free (ESA WorldCover, Dynamic World, Bhuvan).
- M2 requires **no adaptation at all**. `binary_dilation` and `scipy.ndimage.label` are geography-invariant by construction. Area is pixel count × GSD² in Bengaluru exactly as in Bavaria [REV §5.2].

The claim: *symbolic is the only one of the two designs adaptable to India at all, because it localises the entire domain shift into the one component for which Indian supervision exists.*

### 1.6 What the architecture does **not** claim

Stated explicitly so it is not lost [PDF §121–122]:

- The geometry engine cannot recover information M1 failed to segment. If M1 is wrong, M2 is wrong, and the answer is wrong.
- The architecture does not claim symbolic reasoning solves everything. The oracle measurement gives the symbolic *ceiling*; the transfer factor gives the cost of imperfect segmentation.
- The Indian **sensor** gap (Cartosat-2S / RISAT) is not measurable with obtainable data, and no number for it may ever be fabricated [PDF §122; REV §5.6 rule 6].

---

## 2. Complete component inventory

### 2.1 Pipeline components (non-model)

| ID | Name | Pipeline stage | One-line purpose |
|---|---|---|---|
| **V1** | Input validator | 1 | `rasterio`-based check of band count, dtype, CRS, geotransform, shape, NoData, modality, pair co-registration, and metadata-string sanitisation → emits `InputManifest` or a typed rejection [PDF §7]. |
| **P1** | Sensor normalisation | 2 | S1 linear→dB→z-score; S2 20 m→10 m bilinear, 60 m discarded, z-score; both using **frozen training-split statistics**; emits the band-presence mask [PDF §8–10]. |
| **Q1** | Intent + argument parser | 3 | Rule-based parse over the closed template set → `(intent, class_a@level, class_b@level, qualifier)`; CLC synonym table resolves words to class IDs at any hierarchy level [PDF §11–12]. |
| **R1** | Deterministic router + frozen tool registry | 4 | Lookup `(intent × input_config) → ordered tool plan`; parameters bound and Pydantic-validated; no LLM planner, no `eval()`, no dynamic plugin loading [PDF §14–15]. |
| **Scene cache** | Scene cache | 5 | Keyed on `hash(scene_bytes) + model_version`; the map is computed once per scene and serves unlimited queries; a map from a different checkpoint is never served [PDF §17]. |
| **Assembler** | Answer assembler — `src/inference/assembler.py`, class `AnswerAssembler` | 9 | Substitutes M2's number into a template, attaches unit / confidence / evidence refs; enforces the number-flow rule [PDF §78]. |

### 2.2 Models M1–M10

| ID | Name | One-line purpose |
|---|---|---|
| **M1** | Multi-sensor LULC segmenter | Convert 12-channel S1+S2 into a 44-class CORINE-L3 pixel map — the map every symbolic answer is computed from; **the only component carrying the Indian domain gap**. |
| **M2** | Hierarchy-aware symbolic geometry engine | Compute presence, count, area, adjacency, relative position, referring box/point and caption attributes exactly from a class map. Deterministic; **no neural network** [CM §1]. |
| **M3** | Binary VQA decision head | Given a computed quantity, a stated quantity and uncertainty signals, decide YES/NO under a *fitted* tolerance rather than an exact comparison. |
| **M4** | MCQ option scorer | Select one of four options by fitted-metric distance (log scale for area, rank for count) + softmax; uses M5 posteriors for the metadata sub-tasks. |
| **M5** | Scene metadata classifier | Predict country / season / Köppen climate zone from pixels — the 3 of 8 MCQ sub-categories geometry cannot touch. |
| **M6** | Siamese semantic change model | Produce semantic maps for both dates plus a change mask, from which a from-to transition matrix `T[i][j]` is computed. |
| **M7** | VLM (InternVL3-1B + LoRA) | Free-form language, captioning, change narration, RS-adaptation compliance, low-confidence fallback. **Not** counting, area, adjacency, position or boxes. |
| **M8** | Template→style caption rewriter | Rewrite a factually-exact template caption into the dataset's paraphrased surface style. **Conditional — built only if the S8 caption gate says so.** |
| **M9** | Confidence calibrator | Map internal signals to a calibrated `P(answer correct)`; logistic regression + isotonic. |
| **M10** | Query intent classifier | N-way TF-IDF → linear SVM classification of a free-text query, on CPU, when Q1's rules fail. Label set provisional — see §4.1. |

### 2.3 Datasets, services, evaluation and security components

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
| **Sentinel-1/2 over India** | The imagery half of BHARAT-EO — identical sensors, bands and GSD to reBEN, differing only in geography. |
| **ESA WorldCover 10 m v200** | Primary Indian weak pixel labels (11 classes, CC-BY). |
| **Google Dynamic World V1** | Indian weak labels with per-pixel probabilities → confidence weighting. |
| **Bhuvan LULC (NRSC/ISRO)** | Independent coarse Indian cross-check; politically valuable in front of ISRO judges. |
| **Bhoonidhi (Resourcesat / RISAT ≥5 m)** | Unlabelled Indian-sensor domain-shift measurement only. |
| **BHARAT-EO / BHARAT-TRAIN / BHARAT-VAL** | The corpus we build. BHARAT-VAL is held out, never trained or tuned on, used once. |
| **Cartosat-2S / RISAT hidden set** | **Unobtainable.** Never claim a number for it. |

**Services / runtime.** Scene cache; append-only trace store; evidence overlay renderer; PDF report generator; JSON response API; frontend (map, overlay, trace panel, evidence panel — nothing more [REV §7.4]).

**Evaluation components.** Oracle harness (M2 on ground-truth maps); blind question-only baseline; majority-class baseline; class-prior baseline; the **A1 falsification ablation** (six configs, S16); perturbation suite (8 rows); bootstrap CI machinery (resampled over the 1,082 *pairs*, not annotations); McNemar's paired test; per-class IoU table; 44×44 confusion matrix with sibling groups boxed; count-error decomposition (over- vs under-count); per-sub-task error attribution; ECE / Brier / reliability diagram / risk–coverage curve.

**Security components.** V1's typed rejection and metadata-string sanitisation; Q1/M10 input sanitisation (control characters stripped, length capped) as a **prompt-injection defence**, since metadata strings from uploaded files reach that path [REV §3.10]; deterministic routing with no `eval()` and no dynamic plugin loading; Pydantic bounds validation on every bound tool parameter; append-only trace; benchmark-split loader guard raising unless `ALLOW_BENCHMARK_EVAL=1` [CM §7].

---

## 3. End-to-end data flow, per query family

Traced against the **provisional 10-way intent enum** (§4.1). The enum is PROVISIONAL and is replaced by the empirical vocabulary at **Stage S3 (benchmark forensics)** — see §10.2 A5.

### 3.0 The common prefix

Every single-image query runs:

```
GeoTIFF(s) + question
  → V1   validate → InputManifest (or typed rejection)
  → P1   S1 dB + z-score · S2 resample + z-score · band-presence mask
  → Q1   rules → (intent, class_a@level, class_b@level, qualifier)
           └─ on rule failure → M10 (TF-IDF → linear SVM, CPU)
  → R1   (intent × input_config) → Pydantic-validated tool plan + trace header
  → SCENE CACHE   hit → reuse map · miss → run pipeline-stage-5 perception
```

Every family terminates:

```
  → M9         P(answer correct) → high / medium / low band
  → abstention operational: abstain below τ · benchmark: NEVER abstain
  → Assembler  number from M2 substituted into a template
  → JSON + evidence overlay + execution trace + PDF report
```

### 3.1 Component firing matrix

`●` fires · `○` idle · `◐` conditional · `▲` fires but its output is unused

| # | Intent | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `PRESENCE` | ● | ● | ◐ binary | ◐ MCQ | ○ | ○ | ◐ fallback | ○ |
| 2 | `COUNT` | ● | ● | ◐ binary | ◐ MCQ | ○ | ○ | ◐ fallback | ○ |
| 3 | `AREA` | ● | ● | ◐ binary | ◐ MCQ | ○ | ○ | ◐ fallback | ○ |
| 4 | `ADJACENCY` | ● | ● | ◐ binary | ◐ MCQ | ○ | ○ | ◐ fallback | ○ |
| 5 | `RELATIVE_POSITION` | ● | ● | ◐ binary | ◐ MCQ | ○ | ○ | ◐ fallback | ○ |
| 6 | `REFERRING_EXPR` | ● | ● | ○ | ○ | ○ | ○ | ◐ fallback | ○ |
| 7 | `REFERRING_POINT` | ● | ● | ○ | ○ | ○ | ○ | ◐ fallback | ○ |
| 8 | `METADATA_MCQ` | ▲ | ○ | ○ | ● | ● | ○ | ○ | ○ |
| 9 | `CAPTION` | ● | ● | ○ | ○ | ? | ○ | ◐ | ◐ gated |
| 10 | `CHANGE` | ○ | ● | ● | ● | ○ | ● | ◐ narration | ○ |

V1, P1, Q1, R1, scene cache, M9 and Assembler fire for all ten.

---

### 1. `PRESENCE` — "Is there coniferous forest in this image?"

```
  → M1  12×120×120 → logits[44,120,120] + 8× TTA → argmax_map[120,120]
  → M2  step 0  aggregate L3(44) → the CLC level the question asked
         step 1  binary mask · step 2 cleanup · step 3 components
         presence = |components| > 0
  → M3 (binary) or M4 (MCQ) → M9 → Assembler
```
**Idle:** M5, M6, M8; M7 unless M9 drops below τ_low in benchmark mode.
**Robustness:** medium — bounded directly by CLC **sibling confusion**, which is exactly what the benchmark's adversarial "no" answers target (VERIFIED, [REV F1/§3.1]). This is where the multispectral bands earn their keep and an RGB-only competitor loses.

### 2. `COUNT` — "How many water regions are there?"

M2 steps 2–4 are **load-bearing** here in a way they are not for area or presence:

```
  → M2  step 0  aggregate to the queried level    ← CRITICAL (see §5.3)
         step 1  binary mask
         step 2  morphological opening — FITTED kernel
         step 3  connected components — FITTED connectivity (4 vs 8)
         step 4  drop components below the FITTED minimum mapping unit
         count = |components|
  → M3 / M4 → M9 → Assembler
```
**Robustness:** **lowest of all operations** [REV F2]. A single spurious 3-pixel blob changes the answer; a single thin misclassified bridge merges two regions into one. Counting has no averaging.
**Why aggregation must precede components:** counting "how many artificial-surface regions" on an L3 map requires merging L3 siblings into one binary mask *before* running connected components — otherwise a city split into continuous and discontinuous urban fabric counts as two regions when the ground truth says one [REV F1].

### 3. `AREA` — "What is the area of forest in this image?"

```
  → M2  step 0  aggregate · step 1 mask · step 2 cleanup · step 5 regionprops
         area = Σ pixels × GSD², rounded to nearest 1000 m²   (VERIFIED rounding)
  → M3 (binary "is there ~45,000 m² of forest?") or M4 (MCQ) → M9 → Assembler
  → JSON{value: 420000, unit: "m²", confidence, evidence_refs}
```
**Robustness:** **highest of all operations** [REV F2] — area integrates over thousands of pixels, so unbiased per-pixel errors average out. A 5% pixel error rate produces well under 5% area error.
**Open:** whether components dropped by the MMU threshold are excluded from the area sum is **not specified**. See §10.2 A6.

### 4. `ADJACENCY` — "Are forest and water adjacent?"

```
  → M2  aggregate both classes → mask_A, mask_B
         adjacent = binary_dilation(mask_A, k) ∩ mask_B ≠ ∅     (k FITTED)
  → M3 / M4 → M9 → Assembler
```
**Idle:** M5, M6, M8. **M7 does not need to answer the question at all** [PDF §125].
**Robustness:** high — needs only that both classes exist roughly in the right places.
This is the demonstration family: PUBLISHED 55.86% for a ~2T-parameter model versus an exact computation.

### 5. `RELATIVE_POSITION` — "Which region is north of the agricultural area?"

```
  → M2  aggregate both → centroids → sign of centroid delta → 8-way compass
  → M3 / M4 → M9 → Assembler
```
**Robustness:** high — centroids are averages, robust for the same reason as area.

### 6. `REFERRING_EXPR` — "the largest forest region"

```
  → M2  components → regionprops
         filter: 1% ≤ instance area ≤ 50% of image  AND  bbox_fill ≥ 40%   (VERIFIED)
         → argmax / argmin by qualifier → bbox
  → M9 → Assembler
```
**M3 and M4 stay idle** — the output is a bounding box, not a scalar or an option index (DERIVED).
**Robustness:** medium — needs the *correct instance*, not just the correct class; selection error is unforgiving. But the 1–50% area and ≥40% bbox-fill filters remove wrong candidates for free.
**M7** may fire in fallback with grammar-constrained box decoding.

### 7. `REFERRING_POINT` — given a point inside the target, predict the enclosing box

```
  → M2  bbox of the connected component containing the given point
  → M9 → Assembler
```
A **separate benchmark task** from `REFERRING_EXPR`, scored in its own table, and **near-trivial** — one line of `scipy.ndimage`. Architecture A treated referring expression as a single task and left this one on the table entirely [REV §0.1D].

### 8. `METADATA_MCQ` — "Which country was this image acquired in?"

**M1 and M2 are irrelevant to this family** [PDF §127].

```
  → R1  (MCQ + country) → M5 → M4 → M9 → answer
  → M5  ConvNeXt-Tiny, 12-ch stem, 3 heads → 3 posteriors
  → M4  restrict the posterior to the four offered options → argmax
  → M9 → Assembler
```
**Idle:** M2, M3, M6, M7, M8. M1 is marked **▲** because on a cache miss the perception block may compute it in parallel [PDF §6 diagram], but **its output is not used for this answer** (DERIVED).
**Gate:** if the evaluation harness supplies country / season / geolocation alongside each annotation, these become lookups and **M5 is discarded entirely** [PDF §55; REV §3.5]. Checked at S3. Open question #2 in §10.1.

### 9. `CAPTION` — "Describe the image."

```
  → M1 → M2  caption attribute struct:
              presence · per-class contiguous-region counts ·
              per-class and per-instance sizes · pairwise adjacency ·
              tiers: primary >25% · secondary 5–25% · marginal <5%   (VERIFIED)
  → template caption (facts originate here, and only here)
  → M8 if the S8 caption gate says build it, else M7        ← style only
  → M9 → Assembler
```
**Facts originate from M2; language style comes from M7/M8** [PDF §128]. This is the number-flow rule applied to captioning.
**Idle:** M3, M4, M6.
**M5:** marked **?** — season, country and Köppen zone are appended during the *reference* caption generation from external maps (VERIFIED, [REV F4]), but neither document wires M5's posteriors into our caption path. See §10.2 A7.
**The gate that decides M8's existence** [REV §3.8], run at S8 on ground-truth maps with no trained model:

| Oracle caption BLEU-4 | Decision |
|---|---|
| ≥ ~35 | Raw templates suffice — **skip M8 entirely** |
| ~10 – ~35 | **Build M8** — where the review expects to land (PRIOR) |
| < ~10 | Drop the symbolic captioning path — route to M7 |

### 10. `CHANGE` — "What changed between image 1 and image 2?"

The only family with two images, and the only one where **M1 does not fire**.

```
  → V1  additionally performs the pair co-registration check
  → M6  Siamese U-Net, shared encoder
         → map_t1[6,H,W], map_t2[6,H,W], change_mask[H,W]   (SECOND 6-class taxonomy)
         → T[i][j] = |{p : change[p]=1, map_t1[p]=i, map_t2[p]=j}|
  → M2  arithmetic over T — counts, argmax transitions, deltas
  → M3 / M4  (CDVQA's closed 19-category answer set)   [PDF §129]
  → M9 → Assembler
```
**Idle:** M1, M5, M8. **M7** optionally fires for change *narration* (curriculum step 3, [REV §3.7]).
**Why M1 is idle:** M6 uses a different taxonomy (SECOND-6, not CORINE-44) on different imagery. The two paths do not share a map (DERIVED, forced by [REV §3.6/§4.2]).
**Structural point:** the change path is the same thesis repeated — perception (M6) → measurement (M2 over T) → answer. Change VQA is arithmetic over a predicted transition matrix, exactly as the main path is arithmetic over a predicted LULC map [REV §0.1B, VERIFIED].
**Flagged risk — do not resolve yet:** M6's live-inference input (Sentinel-1/2 GeoTIFF pairs) is not bridged to its SECOND/CDVQA training data (aerial optical) anywhere in the architecture document. **Deferred to Stage S17**, to be resolved from direct inspection of the actual downloaded SECOND/CDVQA files. See §10.2 A3 and §9.5.
**Open:** how M3/M4 map onto a 19-way closed answer set is unspecified. See §10.2 A8.

---

## 4. Model & dataset matrix

### 4.1 Provisional intent enum

**PROVISIONAL** — from `STAGE_PROMPTS.md` Stage 9. Adopted to unblock R1's registry and M10's label set. **Replaced by the empirical vocabulary at Stage S3 (benchmark forensics)**, which exists specifically to determine the real vocabulary from actual annotation data. See §10.2 A5.

```python
class Intent(str, Enum):          # PROVISIONAL — resolve at S3
    PRESENCE          = "presence"
    COUNT             = "count"
    AREA              = "area"
    ADJACENCY         = "adjacency"
    RELATIVE_POSITION = "relative_position"
    REFERRING_EXPR    = "referring_expr"
    REFERRING_POINT   = "referring_point"
    METADATA_MCQ      = "metadata_mcq"
    CAPTION           = "caption"
    CHANGE            = "change"
```

M10's classifier width follows this enum and is therefore also provisional: [PDF §13] specifies **8-way** classification, BigEarthNet.txt is described as spanning **15 tasks** [REV §4.2], and this enum has **10** members. None of the three vocabularies is enumerated in either document. S3 resolves it empirically.

### 4.2 The matrix

| Component | Model / method | Dataset | Input (shape / type) | Output (shape / type) | Metric | Training strategy | Purpose |
|---|---|---|---|---|---|---|---|
| **V1** | `rasterio` checks | — | 1–2 GeoTIFFs + str | `InputManifest` \| typed rejection | Rejection correctness on malformed inputs | None | Reject bad input before it corrupts everything downstream |
| **P1** | Deterministic normalisation | reBEN train statistics (frozen, versioned, hashed) | Raw bands | `float32[12,120,120]` + `band_presence[10]` | — | Statistics **fitted on train split only** | Put both sensors on a comparable, leak-free scale |
| **Q1** | Rules over closed templates + CLC synonym table | Benchmark templates | `str` (sanitised) | `(intent, class_a@level, class_b@level, qualifier)` | Parse success rate | None (rules) | Turn text into a typed query |
| **M10** | TF-IDF (word + char n-grams) → linear SVM | ~300 human-paraphrased + auto-generated template permutations | `str` | intent label + confidence | Accuracy, **target ≥98%** | From scratch (seconds, CPU) | Intent fallback when rules fail. Label set = §4.1, PROVISIONAL |
| **R1** | Frozen registry lookup + Pydantic | — | `(intent, input_config)` | Ordered tool plan + trace header | Plan validity | None | Deterministic, auditable execution path |
| **M1** | Dual-encoder U-Net, ConvNeXt-V2-Tiny ×2, 1×1 conv fusion + SE gate, ~30–45M params | reBEN, 229,114 train patches (geographic split) | `float32[12,120,120]` | `logits[44,120,120]` + `argmax_map` + per-pixel top-1 margin | **Downstream symbolic accuracy (primary)**; mIoU @L3-44 / @19 / @coarse-7; per-class IoU; 44×44 confusion matrix; 8-row perturbation table | **FROM SCRATCH** — AdamW lr 3e-4, wd 1e-4, cosine + 5% warm-up, bf16, batch 128, 30–50 epochs; 8× TTA at inference | Produce the map every symbolic answer is computed from |
| **M2** | `scipy.ndimage` + `skimage.measure`. **No neural network.** | Ground-truth maps (S8) → predicted maps (S-refit) | `argmax_map[120,120]` + taxonomy YAML | Typed struct: scalar + per-instance properties | **Oracle exact-match vs released annotations. Target ≥99%** on presence / area / adjacency / rel-pos | **FIT** connectivity, MMU, opening kernel, dilation radius — **twice** (GT maps, then predicted maps) | Compute what can be computed; geography-invariant |
| **M3** | LightGBM (~200 trees, depth 4) or L2 logistic regression | BigEarthNet.txt train annotations, **features from PREDICTED maps** | 12 tabular features (computed, stated, log-ratio, rank-diff, subtype, class, pixel share, class margin, TTA σ, near-MMU count, sibling prior) | `P(yes)` | Accuracy per sub-type (Table 3 layout), ROC-AUC, **ECE**, McNemar vs fixed threshold | **FROM SCRATCH**, class-balanced to match the benchmark | Decide YES/NO under a fitted tolerance, and learn to correct M1's systematic biases |
| **M4** | Fitted-metric distance + softmax (log scale for area, rank for count) | Same | Computed value, 4 parsed options, sub-category, M5 posteriors | argmax option + softmax distribution | Accuracy per sub-task (Pr/A/Cnt/Adj/RP/Loc/S/Clt), **instruction-following = 100% by construction** | **FIT** a handful of parameters | Select an option; never generate one |
| **M5** | ConvNeXt-Tiny, 12-ch stem, 3 linear heads, ~28M params | reBEN metadata (country, date, geolocation) + Köppen lookup from a public 1 km raster | `float32[12,120,120]` | 3 posteriors: country (10), season (4), Köppen (k) | Top-1 per attribute; **derived 4-option MCQ accuracy** (what is actually scored) | **TRANSFER** — ImageNet-init on RGB channels, full fine-tune, a few GPU-hours | Solve the 3 of 8 MCQ sub-categories geometry cannot touch |
| **M6** | Siamese U-Net, **shared** ImageNet-pretrained encoder (ResNet-34 / ConvNeXt-Tiny), 3 heads. Refs: Bi-SRNet, SCanNet | SECOND (2,968 public pairs) → CDVQA official test splits | T1, T2 RGB 512×512 **(training)**; live-inference input unbridged — see §10.2 A3 | `map_t1[6,H,W]`, `map_t2[6,H,W]`, `change_mask[H,W]` → `T[i][j]` | SECOND mIoU / SeK / F1; CDVQA official test accuracy; **mandatory question-only blind baseline** | **TRANSFER** — ImageNet-init, full fine-tune (data-poor: ~1,600 train pairs) | Make change VQA arithmetic over T |
| **M7** | `OpenGVLab/InternVL3-1B` (MIT; Qwen2.5-0.5B base, Apache-2.0) + frozen BEN S1/S2 ViT branches + trainable linear projections + **LoRA r=8, α=32, dropout=0.1** → 5.8M trainable of 1.1B | BigEarthNet.txt captioning subset (stratified subsample — **report the fraction**) | S1/S2/RGB tokens + instruction tokens | Text, under **constrained decoding** | BLEU-4 / ROUGE / METEOR / CIDEr / BERTScore / SBERT-cosine (Table 7 layout) + instruction-following rate | **PEFT.** Curriculum: (1) projections only ~2k steps, (2) joint LoRA + projections on captioning. Do **not** train VQA/MCQ/grounding adapters unless the S16 gate fails | Language, captioning, RS-adaptation compliance, low-confidence fallback |
| **M8** | Flan-T5-base (250M) seq2seq, or LoRA on Qwen2.5-0.5B-Instruct | (our template caption, released caption) pairs — free and exactly aligned | Template caption string | Styled caption string | BLEU-4 / ROUGE / METEOR / CIDEr **+ automated factuality check** (re-extract attributes; they must match) | **FINE-TUNE.** Conditional on the S8 caption gate | Match the dataset's paraphrased surface style without touching the facts |
| **M9** | L2 logistic regression → isotonic regression | Held-out **calibration split** (not train, not benchmark) | 7 features (class margin, TTA answer stability, component-count σ, area interval width, min component margin, band-presence fraction, sibling-confusion prior) | `P(correct)` + high/med/low band | **ECE**, Brier, reliability diagram, **risk–coverage curve** | **FIT.** Refitted on BHARAT-VAL before any Indian confidence claim | Turn "confidence" from a claim into a measured quantity |
| **Assembler** | Template substitution — `src/inference/assembler.py`, `AnswerAssembler` | — | M2 scalar + M9 confidence | JSON + evidence + trace + PDF | — | None | Enforce: a language model may phrase, never produce, the number |

### 4.3 The pretraining decision table — and why it differs per model

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

**M1 from scratch and M6 from pretrained — same team, same week, opposite decisions, for a stated reason.** [REV §3.6] notes this asymmetry is the kind of thing a judge probes.

---

## 5. Dependency & error-propagation map

### 5.1 Determinism marking

| DETERMINISTIC | PROBABILISTIC |
|---|---|
| V1 · P1 · Q1 (rules) · R1 · **M2** · scene cache · abstention policy · **Assembler** · evidence/trace/PDF renderers | M1 · M3 · M4 · M5 · M6 · M7 · M8 · M9 · M10 |

M2 is deterministic **in its logic** while its *parameters* (connectivity, MMU, opening kernel, dilation radius) are fitted from data [REV §3.2]. That distinction matters: a fitting error is silent and systematic, not random.

### 5.2 Dependency graph

```
V1 ──► P1 ──► [M1, M5, M6]           (V1/P1 failure ⇒ total failure)
       Q1 ──► R1 ──► tool plan        (parse/route failure ⇒ wrong path, wrong answer)
        └── M10 (fallback only)

M1 ──► M2 ──► M3 ──┐
        ▲     M4 ──┤
        │          ├──► M9 ──► Assembler ──► JSON / evidence / trace / PDF
M6 ──► T ┘   M7 ──┤        ▲
                   │        │
M5 ──► M4 ─────────┘        │
M1 (margin, TTA variance) ──┘
M2 ──► M7 (attribute struct, JSON — never a sentence)
M2 ──► M8 (template caption)
```

### 5.3 Where an upstream error becomes unrecoverable

Ordered by damage. **Silent** means nothing downstream can detect it.

| # | Failure | Propagates to | Recoverable? | Why |
|---|---|---|---|---|
| 1 | **Loading GeoTIFFs with PIL / OpenCV / `imread`** | Everything | **No — silent and catastrophic** | Silently drops bands beyond 4, silently rescales 16-bit to 8-bit, silently discards CRS and geotransform. Areas come out wrong **by a constant factor** and nothing detects it. [REV §6.1] calls this the most common way a student team quietly ruins a geospatial project. Guarded by V1 + [CM §1]. |
| 2 | **Wrong hierarchy aggregation table** (M2 step 0) | Count, presence, adjacency, rel-pos, ref-expr, caption | **No — silent and systematic** | Counting on an un-aggregated L3 map splits a city into continuous + discontinuous urban fabric → 2 regions where truth says 1. Loses the counting sub-task **systematically**, not noisily [REV F1]. |
| 3 | **M1 segmentation error** | M2 → M3/M4 → M9 → Assembler | **No** — but *quantified* | "If M1 is wrong, M2 is wrong, and the answer is wrong — the geometry engine can't recover information that wasn't correctly segmented" [PDF §121]. This is exactly what the oracle decomposition measures, per sub-task. Partially compensated by training M3/M4 on **predicted** maps so they learn M1's biases [REV F3]. |
| 4 | **Normalisation statistics computed per-image or per-batch** | M1, M5 | **No — silent** | Leaks, and breaks at single-image inference. Must be frozen train-split statistics, versioned and hashed into the model card [REV §6.1]. |
| 5 | **Wrong connectivity (4 vs 8) or MMU** | Count (everything), presence (marginally) | **No — silent and systematic** | "Swings **every** counting answer" [REV §3.2]. One afternoon of fitting prevents it. |
| 6 | **Q1 / M10 misclassifies intent** | The whole tool plan | **No** | R1 executes the wrong plan deterministically and confidently. M10's ≥98% target exists for this reason. |
| 7 | **M6 consistency loss omitted or mis-weighted** | `T[i][j]` → all change answers | **No** | Without the consistency term the three heads disagree and "the transition matrix is nonsense" [REV §3.6]. |
| 8 | **Random (non-geographic) validation split** | Every architecture decision made with it | **No — silent and optimistic** | Adjacent 1.2 km patches are strongly spatially autocorrelated; validation mIoU comes out several points optimistic and you make wrong decisions with a biased instrument [REV F11]. |
| 9 | **Tuning on the benchmark split** | Every reported number | **No** | The number will not survive the hidden set. Guarded by the `ALLOW_BENCHMARK_EVAL=1` loader guard [CM §7]. |
| 10 | **Mixup / CutMix augmentation** | Count, referring, adjacency | **No** | Fabricates region boundaries and changes connected-component counts — destroys the exact topology the symbolic path depends on. Explicitly forbidden [CM §1; REV §6.4]. |
| 11 | M5 error | Metadata MCQ only | Bounded | Contained to 3 of 8 MCQ sub-categories; cannot touch the geometric path. |
| 12 | M7 / M8 error | Caption surface form; fallback answers | **Yes — bounded by design** | The number-flow rule means a language error cannot corrupt a number. M8 regressions are caught by the automated factuality check. |
| 13 | M9 miscalibration | Abstention decisions, fallback rate | Yes | In benchmark mode the system never abstains, so miscalibration costs ranking, not answers. |

**The structural observation:** failures 1, 2, 4, 5, 8 and 9 are all **silent** — they produce confident, well-formed, wrong answers with a clean-looking trace. Every one of them is a *convention* or *plumbing* error, not a model error. This is why the early stages are spent on the parquet, the taxonomy YAML and the fitting sweeps before a single GPU hour is spent.

---

## 6. Implementation plan

### 6.1 The build order

From [PDF §117] / [REV §8.2]. The architecture documents use an **8-week** plan; our execution breakdown is **S0–S26** (`STAGE_PROMPTS.md`), and the two reconcile via that file's Appendix B and [CM §11]. The S-anchors below are the ones fixed at the S0 gate; the full S0–S26 list lives in `STAGE_PROMPTS.md` and is not reproduced here.

| Week | Build | Gate — the number that must exist | S-anchor |
|---|---|---|---|
| **1** | Data pipeline (reBEN → LMDB). **Parse the parquet:** answer grammar, taxonomy level, distractor spacing, metadata fields. Taxonomy YAML + class-mapping layer. Evaluation harness skeleton. Licence audit. | `docs/ANSWER_GRAMMAR.md` exists and answers: which CLC level do questions use; what metadata rides along; how are distractors spaced | **S3** — benchmark forensics |
| **2** | **M2 geometry engine against ground-truth maps.** Fit connectivity / MMU / opening / dilation. **Run the captioning oracle.** Run blind + majority baselines. Start BHARAT-EO collection. | **GATE 1 — oracle symbolic accuracy per sub-task** + oracle caption BLEU-4 (the M8 decision) | **S8** |
| **3** | Train M1 candidates (dual-encoder U-Net, early-fusion baseline, SegFormer-B0) on one harness. Measure downstream symbolic accuracy on predicted maps. Router + stubbed backend. | **GATE 2 — mIoU @L3/19/coarse-7 and TRANSFER factor per sub-task** | **S9** (intent enum / routing), **S13** (gate) |
| **4** | **The A1 falsification ablation** (blind / majority / VLM-only / symbolic-only / hybrid / oracle). M3, M4, M5. Emergency RGB-only VLM adapter. | **GATE 3 — the falsification test.** If symbolic loses on the computable sub-tasks, fall back to the VLM path **now**, with four weeks left | **S16** |
| **5** | M6 + CDVQA conversion. **Re-fit M2's parameters on predicted maps.** M9 calibrator. Frontend against real endpoints. | CDVQA accuracy + question-only blind baseline; ECE + risk–coverage curve | **S17** — includes resolving §10.2 A3 |
| **6** | M7 adapter. M8 if gated in. **BHARAT-VAL evaluation.** Indian adaptation stages 1–2. | **GATE 4 — European and Indian numbers side by side in one table** | **S23** |
| **7** | Full ablation suite. Perturbation table (8 rows). Bootstrap CIs + McNemar tests. Error analysis. PDF report. | The complete results tables, in the paper's layout | — |
| **8** | **Freeze.** No new features. Rehearse. Write the honest-limitations slide. | Nothing new is built | — |

### 6.2 Why the geometry engine and the oracle come *before* training M1

The single most important ordering decision in the plan, and it inverts the reflex ("train the model first").

**Reason 1 — the oracle is the ceiling of the entire strategy, and it costs zero GPU hours.**
`ORACLE(t)` is symbolic accuracy computed on *ground-truth* maps. It requires no trained model at all [REV §6.12]. It answers the question that decides whether the project is viable: *if segmentation were perfect, would this approach work?* Training M1 first would produce a number that conflates two unknowns — "is the idea right?" and "is the segmentation good enough?" — and you could not tell which was binding.

**Reason 2 — a low oracle means the fix is not a model.**
If `ORACLE(t)` is low, the answer grammar has not been recovered: the connectivity convention, the MMU, the dilation radius or the hierarchy aggregation is wrong. That is fixed by mining the parquet, **not** by training [REV §6.12]. Discovering this at S23, after weeks of GPU time, would be fatal to an 8-week project.

**Reason 3 — M2's parameters must be fitted on clean maps first.**
Connectivity, MMU and dilation radius are recovered by sweeping settings against *ground-truth* maps until the released annotations are reproduced exactly [REV §3.2]. You cannot fit a convention and a segmentation error simultaneously — the fit would absorb the model's noise. They are re-fitted against *predicted* maps at S17, once M1's error characteristics are known and separable.

**Reason 4 — the dependency order forces it anyway.**
M3 and M4 must be trained on features computed from **predicted** maps so they learn to compensate for M1's systematic biases [REV F3]. So M1 must exist before M3/M4. And M2 must exist before either, because it produces their input features. The chain `M2 → M1 → M3/M4 → M9` is a hard dependency order.

**Reason 5 — it front-loads falsification.**
S8 and S16 are both designed to be able to kill the plan while there is still time to execute the fallback. [REV §6.13] calls this "a staged bet with a real exit, not a gamble", and notes that stating the exit condition in advance is itself a credibility signal.

### 6.3 What must never be cut

[REV §7.4]: the symbolic path, the evaluation harness, the execution trace, input validation, the oracle experiment, BHARAT-VAL, and the mandatory capabilities as defined in §11.0.

### 6.4 What was deliberately cut from Architecture A

Cross-modal fusion attribution as a runtime service (kept as an *experiment*); the caption stylizer unless the S8 gate admits it; LEVIR-CD/CC; LoveDA; NISAR; the 0.5B LLM query-classification fallback (replaced by M10); test-time adaptation (implement, default OFF); multi-scale training (replaced by scale-consistency augmentation); frontend polish beyond map + overlay + trace panel + evidence panel.

---

## 7. Testing plan

Per [CM §9]: unit + integration + e2e are required; Pydantic validates at boundaries; production logic lives in `src/`, never in notebooks. Synthetic fixtures must be labelled `SYNTHETIC` in filename and docstring [CM §7].

### 7.1 Per-component

| Component | Unit | Integration | Data | Model | Pipeline | Edge case |
|---|---|---|---|---|---|---|
| **V1** | Each check in isolation (bands, dtype, CRS, geotransform, shape, NoData) | V1 → P1 manifest contract | Malformed / truncated GeoTIFF corpus | — | Rejection path returns a typed error, never a crash | 0-band file; 1-band file; mismatched CRS pair; non-co-registered pair; 8-bit vs 16-bit; NaN NoData; **adversarial metadata string** |
| **P1** | dB conversion; bilinear 20→10 m; z-score with frozen statistics | P1 → M1 tensor shape/dtype | **Leakage test: statistics must come from the train split only** | — | Band-presence mask propagates correctly | All-zero band; missing band; single-image inference (no batch statistics available) |
| **Q1** | Each template rule; CLC synonym resolution at L1/L2/L3 | Q1 → R1 typed tuple | — | — | Rule failure → M10 handoff | Empty query; 10k-char query; control characters; **prompt-injection string**; synonym ambiguous across levels |
| **M10** | Vectoriser + SVM fit/predict | Q1 fallback path | Train/test split of paraphrased queries | **Accuracy ≥98%** on held-out human paraphrases | — | Out-of-vocabulary query; below-threshold → clarification, not a guess |
| **R1** | Registry lookup per (intent × input_config), across the full §4.1 enum | Full plan execution | — | — | Every registered intent produces a valid plan | Unknown intent; 1 image for `CHANGE`; 2 images for a single-image intent; **parameter out of Pydantic bounds** |
| **M1** | Forward-pass shapes; each loss term individually; TTA averaging | M1 → M2 map contract | Label integrity; `ignore_index` honoured; class distribution | **Smoke test: overfit 10 batches** [CM §4]; then per-class IoU | Cache key = `hash(bytes) + model_version` | All-one-class patch; unclassified-heavy patch; dropped modality; dropped bands |
| **M2** | **Property-based (Hypothesis)** on synthetic maps with known component structure; **golden-file suite** | M2 → M3/M4/M7 typed structs | Fitted parameters reproduce released annotations | **Oracle exact-match ≥99%** on presence / area / adjacency / rel-pos | Aggregation → mask → cleanup → components → props | Single-pixel component; component touching all four borders; checkerboard; empty mask; component exactly at the MMU threshold; **two regions joined by a 1-pixel bridge** |
| **M3** | Feature construction | M2 → M3 → M9 | Class balance matches the benchmark's balanced options | Per-subtype accuracy, AUC, **ECE**; McNemar vs fixed threshold | — | computed = 0; stated = 0; log-ratio at ±∞ |
| **M4** | Option parsing; fitted distance metric | M5 → M4 for the metadata path | Distractor spacing quantified from the parquet | Per-sub-task accuracy; **instruction-following = 100% by construction** | — | Tied options; unparseable option; option outside the computed range |
| **M5** | 12-ch stem; 3 heads | M5 → M4 | Köppen lookup correctness against the 1 km raster | Top-1 per attribute + derived 4-option MCQ accuracy | — | Patch straddling a country border; a season boundary date |
| **M6** | Siamese weight sharing (**assert the two encoders are the same object**); each loss term | M6 → T → M2 | SECOND split integrity | SECOND mIoU/SeK/F1; **CDVQA + mandatory blind baseline** | Transition-matrix coherence | No change at all; total change; T1 == T2; 2-px shifted T2; **input-format bridge once A3 is resolved at S17** |
| **M7** | Constrained decoding: yes/no logit comparison, length-normalised MCQ log-likelihood, grammar-constrained boxes | M2 attribute struct → M7 (**assert: JSON in, never a sentence**) | Subsample fraction recorded | BLEU-4/ROUGE/METEOR/CIDEr/BERTScore + instruction-following | Fallback rung firing rate | Empty attribute struct; **assert M7 never emits a scored number** |
| **M8** | Seq2seq round-trip | M2 → template → M8 | Aligned (template, released) pairs | BLEU-4 etc. **+ automated factuality check: re-extracted attributes must match the source struct** | — | Caption with 0 classes; with all 44 |
| **M9** | Feature extraction | All heads → M9 | Calibration split used for **nothing else** | **ECE, Brier, reliability diagram, risk–coverage** | Both abstention modes | All features missing; P(correct) exactly at τ |
| **Assembler** | Template substitution | Full e2e | — | — | Trace is append-only and complete | **Assert: no number in the output originates outside M2** |

### 7.2 Cross-cutting suites

**Data tests** [CM §7]: target leakage; train/test contamination; duplicate and near-duplicate leakage (perceptual hash across the corpus); **geographic leakage** (assert no 1° grid cell spans a split boundary); preprocessing leakage (assert normalisation statistics derive from train only).

**The benchmark quarantine test** [CM §7]: a loader guard that **raises** unless `ALLOW_BENCHMARK_EVAL=1`. Test that it raises by default, and that no training or tuning code path can set it.

**Regression tests**: golden files for M2 on a fixed synthetic map set; a frozen small evaluation slice re-run on every commit; the seed-determinism test (same seed ⇒ identical outputs) [CM §8]; assert every saved model records weight hash, config hash, git commit, dataset version and seed.

**Pipeline / e2e**: one test per intent in §4.1 — GeoTIFF + question in, JSON + evidence + trace out. Assert the firing matrix: for `METADATA_MCQ`, **assert M2 was never invoked**; for `ADJACENCY`, **assert M7 was never invoked**; for `CHANGE`, **assert M1 was never invoked**.

**API tests**: schema validation on every response; typed rejection on malformed input; the trace is complete and append-only.

**Security tests**: prompt injection via the query string; prompt injection via **GeoTIFF metadata strings** (this path reaches Q1/M10 [REV §3.10]); assert no `eval()` and no dynamic import exists in the routing path; Pydantic bounds enforcement on every tool parameter.

---

## 8. Accuracy improvement plan

### 8.1 The functional form — this replaces targets

[REV §6.12] refuses to state a target accuracy and gives the *form* the target must take instead. [CM §11] makes this binding: never set an arbitrary target before the measurement exists.

```
For each sub-task t:

    TARGET(t)  =  ORACLE(t)  ×  TRANSFER(t)

    ORACLE(t)   = symbolic accuracy on GROUND-TRUTH maps.
                  Measured at S8. Requires no trained model. Zero GPU hours.
                  This is the ceiling of the entire strategy.

    TRANSFER(t) = predicted-map accuracy ÷ ground-truth-map accuracy,
                  measured on the first segmentation checkpoint. S13.

    If ORACLE(t) is low   → the answer grammar is not recovered.
                            Fix the parquet mining. NOT a model problem.
    If TRANSFER(t) is low → segmentation quality is binding.
                            Spend the effort on M1.
```

This is the honest version of "our target is 85%". When a judge asks *how do you know?*, the answer contains two measurements.

### 8.2 Improvement levers, routed by which factor is binding

**If `ORACLE(t)` is binding** — the conventions are wrong, and no GPU time helps:
- Re-fit connectivity (4 vs 8), MMU, opening kernel and adjacency dilation radius against released annotations until reproduced exactly.
- Fix the hierarchy aggregation table (the F1 error class).
- Re-mine the parquet for the tolerance band and distractor spacing.

**If `TRANSFER(t)` is binding** — segmentation is the constraint:
- Loss composition `L_CE + 0.5·L_Lovász + 0.3·L_hier + 0.2·L_scale` — the hierarchy term specifically targets **sibling confusion**, which is what the benchmark's adversarial "no" answers exploit (VERIFIED). Optimise against the off-diagonal mass *inside* the sibling boxes, not against overall accuracy.
- Class balancing: inverse-**sqrt** frequency weighting **capped at 5×** (full inverse-frequency at 44 classes destabilises training); Lovász auxiliary; stratified oversampling of tail classes at a modest 2–3×; **always report per-class IoU**.
- 8× TTA (4 rotations × 2 flips), logits averaged — reliably worth a point or two and it does **double duty** as M9's strongest confidence feature.
- SWA / last-k checkpoint averaging — one run, no extra inference cost.
- 2–3 model ensemble (U-Net + SegFormer-B0) — **only if there is slack late**; it costs the one-GPU deployment story.
- Re-fit M2's cleanup parameters on **predicted** maps at S17: the optimal cleanup for a noisy map is not the optimal cleanup for a clean one. Architecture A did the first fit and not the second.
- Train M3/M4 on **predicted-map** features so they absorb M1's systematic bias — if the segmenter over-fragments forest, M3 learns the counts run high and shifts the boundary. Free accuracy, invisible to anyone treating tolerance as a constant.

**Hyperparameter policy** [REV §6.6]: **do not run a large sweep.** Fix by convention what the reference recipe fixes. Tune only three things for M1, sequentially, one axis at a time — learning rate (3 log-spaced values), loss weights (2–3 combinations), augmentation strength (on / off / heavy). **~8 runs total.**

### 8.3 Evaluation integrity — the non-negotiables

1. **The benchmark split is quarantined.** 1,082 pairs / 15,029 annotations, touched once, at the end, behind the `ALLOW_BENCHMARK_EVAL=1` guard. Tuning on it is lying to yourself, and the number will not survive the hidden set.
2. **Geographic block CV, k=5** [CM §1]. Random k-fold places near-identical patches on both sides and inflates validation mIoU by several points; you then make architecture decisions with a biased instrument.
3. **Blind baselines are mandatory** [REV F8]: question-only, majority-class per sub-category, and class-prior. If the system does not clearly beat these, the benchmark is measuring priors, not perception — and that must be reported.
4. **The significance floor.** Given the split sizes (~1,700 binary and ~700 MCQ annotations per sub-task): 95% CI ≈ **±2.2 points** at p≈0.7 for binary, **±3.7 points** at p≈0.5 for MCQ. Therefore **do not claim a difference under ~3 points on a binary sub-task or ~4 points on an MCQ sub-task.** State this rule explicitly in the report. Do not hill-climb on differences that small — that is fitting noise.
5. **Bootstrap CIs resample over the 1,082 image pairs, not over annotations.** Annotations within a pair are correlated; resampling them independently produces intervals that are too narrow.
6. **McNemar's test** for every paired comparison — both systems answer identical items, so McNemar is correct and far more powerful than comparing independent proportions.
7. **Every fitted preprocessing parameter is fitted on training data only** [CM §7] — normalisation statistics, class weights, TF-IDF vocabulary, scalers, MMU / dilation / connectivity.
8. **Report both domains in every table.** European mIoU and Indian coarse-7 mIoU side by side, in every experiment row. "The moment you allow a European-only number into a slide, you have started deceiving yourself" [REV §5.6].
9. **Record predictions in advance.** §10.3 lists falsifiable PRIORs about the *shape* of results. Check them late and **report both the hits and the misses**.
10. **Matched-compute comparison.** Report GPU-hours for both paths. "We match a per-task fine-tuned VLM at ~1/N of the training compute" is a stronger and more defensible claim than raw accuracy.

### 8.4 The A1 falsification experiment (GATE 3, Stage S16)

Six configurations, scored **per sub-category, on identical questions** [REV §6.13]:

| Config | Method | What its row tells you |
|---|---|---|
| **Blind** | Question text only, no image | If close to our system, the benchmark measures language priors, not perception |
| **Majority** | Most frequent answer per sub-category | The floor |
| **VLM only** | Fine-tuned M7 answers everything | The published-baseline path |
| **Symbolic only** | Geometry engine answers everything computable | The bet |
| **Hybrid (ours)** | Router: computable → symbolic, generative → VLM | Whether the router earns its complexity |
| **Oracle** | Geometry engine on **ground-truth** maps | Separates "the idea is wrong" from "the segmentation is imperfect" — the most valuable row, and one nobody else will have |

**The falsification condition, stated in advance:** *a predicted LULC map plus deterministic geometry will beat a fine-tuned VLM on counting, area, adjacency, relative position and referring expressions, at a fraction of the training compute.* If it fails at S16, fall back to the VLM path with four weeks left.

---

## 9. Risk register

Likelihood and impact are my assessment (DERIVED) unless the documents rank them; the risks themselves are from [REV F1–F12, §5, §7] and [PDF §117, §121–122].

### 9.1 Technical

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| Hierarchy aggregation not implemented or wrong (the F1 error) | Med | **Critical** | Counting oracle accuracy low while presence/area oracle is high | Taxonomy YAML as a first-class object, built early; aggregation is M2 step 0 and runs **before** connected components; golden-file tests |
| Wrong connectivity / MMU convention | **High** | High | Oracle count accuracy < 99% while area accuracy ≈ 100% | Exhaustive sweep against released counts at S8; re-fit on predicted maps at S17 |
| GeoTIFF loaded with PIL/OpenCV somewhere in the codebase | Med | **Critical** | Areas wrong by a constant factor; CRS missing from the manifest | `rasterio` only [CM §1]; V1 asserts geotransform present; a lint test banning `PIL`/`cv2`/`imread` in `src/` |
| Normalisation statistics leak (per-image or per-batch) | Med | High | Validation mIoU good, single-image inference bad | Frozen, versioned, hashed statistics file; explicit leakage test |
| Counting is the weakest sub-task and stays weak | **High** | Med | Count TRANSFER factor far below area's | Predicted-map re-fit of opening/MMU; count-error decomposition (over- vs under-count have **opposite** fixes: opening vs closing) |
| M6's three heads disagree → incoherent transition matrix | Med | High | Change mask contradicts `argmax(map_t1) ≠ argmax(map_t2)` | The `0.3·consistency` loss term is mandatory; assert coherence in tests |
| Mixup/CutMix silently introduced by a well-meaning team member | Med | High | Counting accuracy drops with no other explanation | Explicitly forbidden [CM §1]; add to the augmentation config schema as a rejected key |

### 9.2 Data

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| **Geographic leakage** in the internal validation split | **High** | High | Validation mIoU implausibly high; small train/val gap | Block by country / 1° grid / S2 tile ID; assert no cell spans a boundary |
| Benchmark split contaminated by tuning | Med | **Critical** | Any code path reads it before final evaluation | `ALLOW_BENCHMARK_EVAL=1` loader guard; test that it raises by default |
| Answer grammar not recovered from the parquet | Med | **Critical** | Oracle accuracy low across **all** sub-tasks | S3 is dedicated to this; `ANSWER_GRAMMAR.md` is its gate |
| Licence status of SECOND / CDVQA / VRSBench / reBEN checkpoints unresolved | Med | High | No licence table exists by the end of S3 | Licence audit at S3; a table, not a hesitation |
| reBEN pretrained checkpoints were trained on train+val+test → leakage | Low | High | — | Check the model cards at S3 (open question #9) |
| WorldCover / Dynamic World label noise poisons Indian adaptation | **High** | Med | Indian fine-tuning degrades European mIoU without improving Indian | Confidence-weighted pseudo-labels; train on inter-source **agreeing** pixels; tag weak labels in the dataset index and never average them into a headline number |
| Near-duplicate patches across the internal split | Med | Med | — | Perceptual hash across the corpus |

### 9.3 Model

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| L3-44 mIoU very low and drags everything | Med | High | **If L3 mIoU < ~25, something is wrong with the label loading, not the model** [REV §3.1] | Check the loader first; report mIoU at L3/19/coarse-7 and per-class always |
| S8 caption gate lands in the "drop symbolic captioning" band (<10 BLEU-4) | Med | Med | The S8 oracle caption score | Route captioning to M7; the gate is designed to make this a cheap decision |
| M5 turns out unnecessary (harness supplies metadata) | Med | Low | S3 parquet inspection | Discard the model — this is a *good* outcome, not a loss |
| Over-adapting to India destroys European performance | Med | High | European mIoU drops > ~2 points | **The replay-and-stop rule:** interleave European batches at 20–30%; back off if European mIoU drops >2 points |
| Not reproducing the published 34.04 BLEU-4 | **High** | Low | — | **Say so up front.** Compare against InternVL3-1B **zero-shot** (0.45 BLEU-4, 54.11 binary, 26.76 MCQ, 5.76 ref-exp), which is the fair and winnable comparison; report the subsample fraction honestly |

### 9.4 Security

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| Prompt injection via **GeoTIFF metadata strings** reaching Q1/M10 | Med | Med | — | V1 sanitises metadata strings; Q1/M10 strip control characters and cap length |
| Prompt injection via the query string | Med | Low | — | Closed intent vocabulary; M10 is a linear SVM with no generative surface |
| Arbitrary execution via a dynamic tool path | Low | **Critical** | — | **No `eval()`, no dynamic plugin loading, no LLM planner** [CM §1]; frozen registry; Pydantic bounds |
| Malformed / hostile GeoTIFF crashes the service | Med | Med | An untyped exception escapes V1 | V1 returns a typed rejection; fuzz corpus of malformed rasters |

### 9.5 Integration

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| **M6 input-format mismatch** — live inference takes Sentinel-1/2 GeoTIFF pairs; M6's SECOND/CDVQA training data is aerial optical. The architecture document does not bridge them. | **High** | High | The change path cannot run on a real hidden-set input | **Flagged, deliberately unresolved at S0.** Deferred to **Stage S17**, to be resolved from direct inspection of the actual downloaded SECOND/CDVQA files — **not** from general dataset literature. No bridging strategy is chosen now. See §10.2 A3. |
| A component consumes another's natural language | Med | High | A sentence appears in an inter-component payload | Typed structures at every boundary; e2e test asserting M7 receives JSON, never a sentence |
| A number is parsed back out of generated text | Low | **Critical** | — | The number-flow rule [CM §2]; the Assembler asserts provenance |
| Scene cache serves a map from a different checkpoint | Low | High | Irreproducible results between runs | Cache key = `hash(scene_bytes) + model_version` |
| The provisional intent enum (§4.1) does not match the real vocabulary | **High** | Med | S3 forensics finds intents outside the enum, or unused members | The enum is explicitly PROVISIONAL; R1's registry and M10's label set are built to be regenerated from it at S3 |

### 9.6 Performance

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| Cannot fit segmenter + VLM on one 24 GB GPU | Low | Med | OOM late in the plan | Architecture B is sized for one 24 GB GPU "comfortably"; M7 is 1.1B with 5.8M trainable |
| 8× TTA makes inference too slow for a live demo | Med | Low | Per-query latency in the trace | The scene cache means the map is computed **once** per scene and serves unlimited queries |
| GPU not secured early | Low | **Critical** | — | **This is the documented trigger to build Architecture C instead** [REV §7.3] |

### 9.7 Delivery & demonstration

| Risk | L | I | Early-warning signal | Mitigation |
|---|---|---|---|---|
| **Scope overrun — arriving late with six half-built components and no measured numbers** | **High** | **Critical** | Any stage's gate number does not exist | [REV F9] names this **the single highest-probability failure mode of the project** — above any architectural error. Architecture B is deliberately smaller than A; the final stage is a hard freeze; §6.4 lists what was cut |
| Uncontrolled feature development | **High** | High | New features appearing after the S23 gate | [PDF §117] names this one of the largest project risks. The last stage builds nothing new |
| Fewer than 4 of 6 members can commit substantial time | Med | **Critical** | — | **Documented trigger to build Architecture C.** "Do not build a half-finished B. A complete simple system beats an incomplete sophisticated one, every time, in front of judges who can only evaluate what runs" [REV §7.3] |
| A **mandatory capability** (§11.0) is incomplete at freeze | Med | **Critical** | A query family in the answer grammar has no working end-to-end path; or an output artifact is missing; or BHARAT-VAL was never run | §11.0 defines the three capabilities from the architecture document alone; §11.5 tracks them as explicit checkboxes; they are on the never-cut list (§6.3) |
| A mixed-provenance number appears on a slide | Med | Med | A table cell without a source | Fix the provenance of **every** cell — [REV §0.1E] notes Architecture A mixed three tables into one row, and "if you put that in front of the authors' colleagues at SAC, someone will notice" |
| Claiming a Cartosat/RISAT number | Low | **Critical** | Any Indian-sensor accuracy figure appears | **Never.** Report the four-axis gap table and the perturbation suite instead. A SAC judge will know the difference immediately |
| Demo fails live | Med | High | — | The final stage is rehearsal only; the scene cache makes repeat queries fast; abstention in operational mode names the failing class rather than guessing |

---

## 10. Assumptions & ambiguities

§10.1 holds the architecture's own open questions. §10.2 holds the items resolved or logged at the **S0 gate**, all under **ASSUMPTION — REQUIRES VALIDATION**. §10.3 records falsifiable performance PRIORs.

### 10.1 The architecture's own open questions [REV Appendix B]

| # | Question | Why decision-critical | Resolve at |
|---|---|---|---|
| 1 | At which CLC level do the benchmark's questions name classes — L1, L2, L3, or mixed? | Determines the segmentation target and the aggregation table. **The single highest-impact unknown.** | **S3**, from the parquet |
| 2 | What metadata rides along with each annotation (season, country, climate zone, geolocation)? | Decides whether M5 is a model, a lookup, or a discard | **S3**, from the parquet |
| 3 | Connectivity convention: 4 or 8? | Swings **every** counting answer | **S8**, by fitting against released counts |
| 4 | Distractor spacing for MCQ area and count | Tells you precisely how accurate M1 must be — a design input, not a post-hoc observation | **S3**, from the parquet |
| 5 | Tolerance band for binary area/count "yes" | Determines M3's feature design | **S8** |
| 6 | Does "or the any open source training data" in the problem statement permit corpora beyond BigEarthNet.txt? | **If denied, the change path is impossible** — BigEarthNet.txt is single-timestamp, so some external corpus must be permitted | Blocked on the problem statement — see A1 |
| 7 | Does the ISRO/SAC hidden set exercise all five capabilities, or focus on the cross-modal pair? | If cross-modal is central it deserves more investment than its benchmark weight implies | Blocked on the problem statement — see A1 |
| 8 | Licence status of SECOND, CDVQA, VRSBench and the reBEN pretrained checkpoints | "Are your training data legally usable?" should get a table, not a hesitation | **S3** |
| 9 | Were the reBEN pretrained checkpoints trained on train only, or train+val+test? | If the latter, using them leaks into the evaluation | **S3**, from the model cards |
| 10 | Is Bhoonidhi data at ≥5 m genuinely open for a non-government entity under current policy? | A policy claim made on stage in front of SAC judges must be right | **S3** — verify directly, do not repeat a second-hand claim |

### 10.2 Logged at the S0 gate — ASSUMPTION — REQUIRES VALIDATION

**A1 — "Mandatory capabilities" defined from the architecture document alone.**
**ASSUMPTION — REQUIRES VALIDATION:** the external problem-statement document (SIH26167) was not supplied and is out of scope for this project. Both architecture documents reference "the five mandatory capabilities" / "the five mandatory clauses" ([REV §7.2], [REV §7.4], [PDF §113]) without ever enumerating them. **"Mandatory capabilities" is therefore taken to mean the deliverables the architecture document names explicitly**, defined in §11.0. If the problem statement is later supplied and its list differs, §11.0 and §9.7 must be revised.
*Not blocking. Owner: human, if and when the problem statement becomes available.*

**A2 — S0–S26 stage numbering. CLOSED at S1.**
**RESOLVED at the S0 gate:** S0–S26 is our own execution breakdown, defined in `STAGE_PROMPTS.md`. It is not the architecture document's numbering — the PDF has only an 8-week plan. The two reconcile via `STAGE_PROMPTS.md` Appendix B and [CM §11]. No edit is required to `CLAUDE.md` or to either architecture document.
**CLOSED at S1:** `STAGE_PROMPTS.md` was committed to the repository and read in full (1,558 lines). Every anchor used at the S0 gate is confirmed correct against it: S3 benchmark forensics, S7 M2 geometry engine, S8 GATE 1 (oracle + blind baselines), S9 Q1/M10 intent, S13 GATE 2 (transfer factor), S16 GATE 3 (A1 falsification), S17 M6/CDVQA, S23 GATE 4 (BHARAT-EO). Appendix B's verified week mapping:

| Week | Stages | Deliverable |
|---|---|---|
| 1 | S0–S4 | `ANSWER_GRAMMAR.md`, taxonomy, data pipeline, licence audit |
| 2 | S5–S8 | **Oracle accuracy + oracle BLEU (GATE 1)** |
| 3 | S9–S13 | **Transfer factor (GATE 2)** |
| 4 | S14–S16 | **Falsification test (GATE 3)**, M3/M4/M5 |
| 5 | S17–S18 | CDVQA accuracy, ECE, risk–coverage |
| 6 | S19–S23 | Europe and **India results (GATE 4)** side by side |
| 7 | S24–S25 | Ablations, bootstrap CIs, McNemar, error analysis, PDF report |
| 8 | S26 | Freeze, rehearse, finalise limitations and presentation |

*Closed. No further action.*

**A3 — M6 input-format mismatch. Deliberately unresolved.**
**ASSUMPTION — REQUIRES VALIDATION:** M6's live-inference input (Sentinel-1/2 GeoTIFF pairs) versus its SECOND/CDVQA training data (aerial optical, RGB 512×512, 0.5–3 m GSD, Chinese cities) is **not bridged in the architecture document**. **Deferred to Stage S17**, to be resolved from **direct inspection of the actual downloaded SECOND/CDVQA files** — not from general dataset literature. **No bridging strategy is chosen now.** Tracked as a High/High integration risk in §9.5.
*Not blocking before S17. Owner: S17.*

**A4 — "A1" naming collision. RESOLVED.**
`A1` is reserved **exclusively** for the Stage S16 falsification experiment, matching the architecture document's own usage. The pipeline-stage-9 output-assembly component is named **Assembler** — `src/inference/assembler.py`, class `AnswerAssembler`, no letter-number code. Applied throughout this document and binding on all future stages.
*Closed.*

**A5 — Query family / task-count enumeration. Deferred to S3.**
**ASSUMPTION — REQUIRES VALIDATION:** three different task vocabularies appear across the sources and **none is enumerated**: M10 is specified as **8-way** [PDF §13]; BigEarthNet.txt is described as spanning **15 tasks** [REV §4.2, §1.4]; the provisional enum in §4.1 has **10** members. This is **not resolved from the documents.** The provisional 10-way enum from `STAGE_PROMPTS.md` Stage 9 is adopted to unblock R1's registry and M10's label set, and is marked PROVISIONAL wherever it appears (§3, §4.1, §7.1). **Stage S3 (benchmark forensics) exists specifically to determine the real vocabulary from actual annotation data** and supersedes the enum.
*Not blocking. Owner: S3.*

**A6 — Does area exclude MMU-dropped components?**
[REV §2.2] presents M2's steps 0–5 as one sequence with `area = Σ pixels × GSD²`. Whether the sum runs over the *cleaned, MMU-filtered* mask or the *raw* aggregated mask is not stated. It changes every area answer. **ASSUMPTION — REQUIRES VALIDATION** — resolvable empirically at S8 by fitting both variants against released area annotations.

**A7 — Is M5 wired into the caption path?**
Season, country and Köppen zone are appended during *reference* caption generation from external maps (VERIFIED, [REV F4]). Neither document says whether our caption attribute struct should include M5's posteriors. If the reference captions carry those attributes and ours do not, n-gram overlap is lost for free. **ASSUMPTION — REQUIRES VALIDATION** at S8 against released captions.

**A8 — How do M3/M4 map onto CDVQA's closed 19-category answer set?**
[PDF §129] shows `M6 → T → M2 → M3/M4 → M9`, so they do fire. But CDVQA's answers are a **closed set of 19 categories** [REV §4.2] — a 19-way selection, not a binary decision or a 4-option MCQ. The mapping is unspecified. **ASSUMPTION — REQUIRES VALIDATION** at S17.

**A9 — The M1→India stop-rule threshold is approximate.**
"Back off if European mIoU drops by more than ~2 points" [REV §5.5]. The `~` is doing real work, and it is stated on mIoU while §8.3's significance floor is stated on sub-task accuracy, so the two are not directly comparable. The threshold must be made exact before S23. **ASSUMPTION — REQUIRES VALIDATION.**

**A10 — Köppen zone class count `k`.**
"k determined by what appears in reBEN" [REV §3.5]. Not yet known. **UNKNOWN — S3, from the metadata.**

**A11 — Canonical PDF filename.**
[CM §0] names `docs/architecture/SatQuery_Architecture.pdf`; the repo file is `SatQuery_Architecture (1) (1).pdf` (a browser-duplicated filename). Content verified as Architecture B and consistent with [CM §1]'s frozen facts. **Recommend renaming so [CM §0] resolves.** *Minor — fix before anyone else clones the repo.*

### 10.3 Unvalidated performance expectations (PRIORs — not targets)

Recorded in advance so the late stages can check them, per [REV §6.12]:

- Area will be the **strongest** symbolic sub-task; **counting the weakest** — the reverse of Architecture A's assumption.
- Presence will be bounded by CLC **sibling confusion**, not by method.
- `REFERRING_POINT` should be near-trivial; `REFERRING_EXPR` should be strong.
- Captioning is the **highest-variance** outcome; the S8 gate decides it.
- MCQ overall is **capped** by the three metadata sub-tasks, which no geometry can solve.
- M1 L3-44 mIoU PRIOR range 30–50, coarse-7 75–88 — **moderate confidence, dragged down by the long tail. Measure at S13 and replace the table.**

**None of these are targets.** [CM §11]: never set an arbitrary target before the measurement exists.

---

## 11. Definition of done

### 11.0 "Mandatory capabilities" — the working definition

**ASSUMPTION — REQUIRES VALIDATION** (§10.2 A1): the external problem-statement document was not supplied. "Mandatory capabilities" is taken to mean **the deliverables the architecture document names explicitly**, and nothing else:

| # | Capability | Source |
|---|---|---|
| **MC-1** | The **full 9-stage pipeline** (§1.2) runs end-to-end for **every query family in the answer grammar** | [PDF §6, §7–79] |
| **MC-2** | All four output artifacts are produced: **structured JSON**, **evidence overlay**, **append-only execution trace**, and **PDF report** | [PDF §79; REV §2.2 stage 9] |
| **MC-3** | The **BHARAT-VAL Indian evaluation** is run and reported | [PDF §93–95, §118; REV §5.3, §5.6] |

"Every query family in the answer grammar" is resolved empirically at **S3**, not from the provisional enum in §4.1. These three are on the never-cut list (§6.3) and are tracked as checkboxes in §11.5.

### 11.1 Measurement completeness

- [ ] **GATE 1 (S8)** measured and reported: oracle symbolic accuracy per sub-task, on ground-truth maps.
- [ ] **GATE 2 (S13)** measured and reported: transfer factor per sub-task = predicted ÷ oracle.
- [ ] **GATE 3 (S16)** measured and reported: the six-config **A1** falsification table, per sub-category, on identical questions.
- [ ] **GATE 4 (S23)** measured and reported: BHARAT-VAL coarse-7 mIoU, **next to** the European number.
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

- [ ] The number-flow rule holds everywhere: no scored number originates outside M2. **Asserted in tests, not just documented.**
- [ ] No component consumes another component's natural language.
- [ ] Routing is deterministic: no LLM planner, no `eval()`, no dynamic plugin loading; all parameters Pydantic-validated.
- [ ] `rasterio` only for GeoTIFFs — enforced by a test, not a convention.
- [ ] No Mixup/CutMix anywhere in the augmentation path.
- [ ] The naming conventions fixed at S0 hold throughout the codebase: `A1` = the S16 experiment only; the assembler is `AnswerAssembler` in `src/inference/assembler.py`; `S1` = Sentinel-1 only.
- [ ] Zero architecture deviations in `PROJECT_STATUS.md`, or each one carries an approved `=== PROPOSED ARCHITECTURE CHANGE ===` record [CM §6].

### 11.4 Reproducibility

- [ ] Global seed set for `random` / `numpy` / `torch` / CUDA and recorded in every result artifact.
- [ ] Every saved model records weight hash, config hash, git commit, dataset version, seed.
- [ ] All parameters in `configs/*.yaml`; no magic numbers in `src/`.
- [ ] `make reproduce` rebuilds the pipeline from a clean environment.
- [ ] A dataset card exists in `docs/datasets/` for every dataset used.
- [ ] Normalisation statistics are frozen, versioned and hashed into the model card.

### 11.5 System completeness — the mandatory capabilities

- [ ] **MC-1** — all nine pipeline stages implemented; **every query family in the S3-confirmed answer grammar** runs end-to-end.
- [ ] **MC-1** — each family has a passing e2e test asserting the **firing matrix** (§3.1).
- [ ] **MC-2** — structured JSON produced.
- [ ] **MC-2** — evidence overlay produced (mask overlay, numbered component contours, boxes, per-component area table, margin heatmap, GeoJSON/GeoTIFF export).
- [ ] **MC-2** — append-only execution trace produced (task, tools, bound parameters, per-stage timings, model name + weights hash).
- [ ] **MC-3** — BHARAT-VAL evaluation run and reported at coarse-7, alongside the European number.
- [ ] Both abstention modes work; the fallback-rung firing rate is measured and reported.
- [ ] Runs locally on one GPU.
- [ ] Security tests pass, including prompt injection via GeoTIFF metadata strings.

### 11.6 Honesty

- [ ] **No Cartosat/RISAT accuracy number is claimed anywhere.**
- [ ] The four-axis Indian gap table (spectral / spatial / SAR / geographic) is presented with the three simulable axes measured and the sensor axis stated as unmeasurable.
- [ ] The 8-row perturbation table is published **in full, including the rows where we lose**.
- [ ] The honest-limitations slide exists: M1 quality is the ceiling; the Indian sensor gap is unmeasured; 34.04 BLEU-4 was not reproduced, and why.
- [ ] The late-stage check of §10.3's advance predictions reports **both the hits and the misses**.
- [ ] The M7 training subsample fraction is reported.
- [ ] Every performance claim is labelled PUBLISHED, measured, or PRIOR — never presented as fact when it is an expectation.
- [ ] Every §10.2 ASSUMPTION is either validated and closed, or carried into the final report as a stated limitation.

### 11.7 Open items carried forward

- [ ] §10.2 **A1** — if the SIH26167 problem statement becomes available, reconcile §11.0 against its actual capability list.
- [x] §10.2 **A2** — CLOSED at S1: `STAGE_PROMPTS.md` committed and read; all S-anchors verified.
- [ ] §10.2 **A3** — M6's input-format bridge resolved at S17 from direct inspection of the downloaded SECOND/CDVQA files.
- [ ] §10.2 **A5** — the provisional intent enum replaced by the S3-confirmed vocabulary; R1's registry and M10's label set regenerated.
- [ ] §10.2 **A6–A10** closed, each with a recorded answer.
- [ ] §10.2 **A11** — PDF renamed so [CM §0] resolves.
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

*Stage S0 deliverable. Records comprehension only. No code written, no metric measured, no dataset downloaded. Every ASSUMPTION and UNKNOWN in §10 is unresolved as of 2026-08-29.*
