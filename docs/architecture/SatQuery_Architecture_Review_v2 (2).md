# SatQuery AI — Critical Architecture Review and Final Technical Specification

**Reviewing:** `SatQuery_AI_Architecture.pdf` (58 pp., prepared 24 Aug 2026)
**Context:** SIH26167 · ISRO / Department of Space
**Date of this review:** 29 August 2026

---

## 0. Evidence labels used in this document

| Label | Meaning |
|---|---|
| **VERIFIED** | I opened the primary source during this review and read the relevant passage. |
| **PUBLISHED** | A number transcribed from a peer-reviewed / arXiv table I read directly. |
| **PRIOR** | My engineering expectation. Not measured, not published. Stated so you can falsify it. |
| **UNKNOWN** | Genuinely unresolved. Named owner + deadline required. |
| **CORRECTION** | Something in the previous document that is wrong or misleading. |

Every performance number below is one of: PUBLISHED (with source), PRIOR (with reasoning), or explicitly marked as unavailable. **Where no reliable published number exists for our exact setup, this document says so instead of inventing one.** That happens more often than you might like — see §3.

---

## 0.1 What I verified in this session, and what it changed

I read the following primary sources directly:

- **arXiv:2603.29630** — *BigEarthNet.txt: A Large-Scale Multi-Sensor Image-Text Dataset and Benchmark for Earth Observation* (Herzog, Adler, Hackel, Shu, Zavras, Papoutsis, Rota, Demir — TU Berlin/BIFOLD, Trento, NTUA/NOA). Full text including §3.1 annotation pipeline and Tables 2–8.
- **arXiv:2605.03189** — *Sentinel2Cap*, which documents reBEN's label structure independently.
- **arXiv:2112.06343** — *Change Detection Meets Visual Question Answering* (the CDVQA paper).
- **arXiv:2604.18429** — a 2026 CDVQA re-evaluation paper, for current split statistics.
- NRSC/Bhuvan thematic services documentation for Indian LULC products.

Five things changed as a result. In order of how much they matter:

**A. The segmentation taxonomy question is now answered, and the answer is not the one the document assumed.**
The previous document specifies a 19-class segmentation head with a `NEEDS CONFIRMATION: 19 vs CLC Level-3` flag. The evidence says: reBEN's **pixel-level reference maps use CORINE Level-3, which is 44 classes**. The 19-class scheme is reBEN's *image-level* multi-label vocabulary, inherited from BigEarthNet v1. These are different label products in the same dataset. Building a 19-class segmentation head against L3 reference maps means either collapsing your supervision (losing exactly the sibling distinctions the benchmark is designed to punish) or silently mismatching your labels. **This single fact invalidates the segmentation spec in §12.2 of the previous document and it cascades into every downstream accuracy estimate.** Resolution in §2 and §3.1 below.

**B. The CDVQA hypothesis is confirmed, and it upgrades from LIKELY to VERIFIED.**
The previous document flagged as `LIKELY` that CDVQA was auto-generated from SECOND's semantic change masks. It was. The CDVQA paper states plainly that SECOND was chosen as the base data and question–answer pairs were generated automatically from its pixel-level semantic change maps over six land-cover classes. Answers fall into a closed set of 19 categories. **The change path is therefore arithmetic over a predicted from-to transition matrix, exactly as the document hypothesised.** The week-1 investigation task can be closed now.

**C. The captioning hypothesis (H-CAP) is over-optimistic as stated.**
The paper's §3.1 confirms captions are template-generated from the reference maps — so far so good. But it also specifies that a **quantised Llama-4-Scout-17B** paraphrasing stage was explicitly instructed to *diversify lexical and syntactic structure*, followed by a self-refinement pass, and that the prompt supplied the CLC nomenclature to permit synonym substitution across hierarchy levels. Every one of those design choices is directly adversarial to n-gram overlap. Meanwhile RS-InternVL was fine-tuned on those paraphrased captions, so its BLEU-4 of 34.04 partly reflects having *learned the paraphrase style*. My PRIOR: raw template captions will score materially **below** 34.04, not above it. The document's proposed fix (a learned template→style rewriter) is the right one and is cheap; it should be planned for from the start rather than treated as a contingency. See §3.8.

**D. Referring-expression constraints confirmed, with a second one the document missed.**
VERIFIED: referring LULC detection targets instances covering **1–50% of image area and at least 40% of their enclosing bounding box**. The document has this. What it does not have: **referring *point* detection is a separate task** where the model is given a point inside the target and must predict the enclosing box, and it is scored in its own table. That is an even easier symbolic operation than referring LULC detection — given a point, the answer is the bounding box of the connected component containing that point. One line of `scipy.ndimage`. The document treats referring expression as a single task and leaves the easier of the two on the table.

**E. Minor transcription errors in the previous document's tables.**
The candidate matrix in §7.1 lists InternVL3-1B as "5.01 mIoU / 54.11 binary / 0.34 BLEU-4". Those three numbers come from three different tables in the paper (referring *LULC* detection Table 5, binary VQA Table 3, captioning Table 7). The paper's headline Table 2 gives InternVL3-1B as 0.45 captioning / 54.11 binary / 26.76 MCQ / 5.76 ref-exp, where the ref-exp column aggregates both referring tasks. Not a big deal, but if you put a mixed-provenance row on a slide in front of the authors' colleagues at SAC, someone will notice. Fix the provenance of every cell.

---

# 1. Review of the previous architecture

## 1.1 The headline verdict

**The core architectural bet is correct and I am not overturning it.**

The bet is: *the benchmark's ground truth is a deterministic function of a pixel-level reference map, therefore predict the map and compute the answers rather than generating them.* I checked this against §3.1 of the paper and it holds. Captions are built by extracting presence, per-class contiguous-region counts, per-class and per-instance sizes, and pairwise adjacency directly from the reference maps, with areas rounded to the nearest 1000 m² and classes tiered by coverage (>25% primary, 5–25% secondary, <5% marginal). Binary and MCQ annotations are generated from those same four spatial categories. Referring expressions are generated from instance geometry with explicit area and bbox-fill constraints.

That is not a perceptual task. It is measurement. The published numbers show the field currently treats it as perceptual and pays for it: a frontier general-purpose model with a reported ~2T parameters reaches 55.86% on binary adjacency, against a balanced yes/no set — under six points above chance — while `scipy.ndimage.binary_dilation` computes the same relation exactly (PUBLISHED, Table 3).

So the strategy is sound. What follows is a critique of the *engineering* of that strategy, and there is a fair amount to say.

## 1.2 Weaknesses, ranked by how much score they cost

### **F1 — The taxonomy error (critical)**

Covered in §0.1A. To restate the consequence in engineering terms: the previous document's §12.2 specifies `head: 1x1 conv -> 19 classes` and its accuracy targets in §28.2 (counting >85, area >80, adjacency >85) are implicitly priced for a 19-way dense-prediction problem. The actual supervision is **44-way**, with a severe long tail — CORINE L3 includes classes like *Salines*, *Burnt areas*, *Glaciers and perpetual snow* that appear in a vanishing fraction of European patches.

Three consequences:

1. **mIoU will be much lower than a 19-class number would suggest.** With 44 classes and a long tail, the arithmetic mean IoU is dragged down by classes with a handful of training pixels. Any mIoU figure quoted without stating the class count is meaningless.
2. **Connected-component counting gets harder, not easier, at L3.** More classes means more boundaries, more fragmentation, more spurious components. Counting is the most fragility-sensitive of all the symbolic operations (see F2).
3. **But — and this is the recovery — the questions are not necessarily asked at L3.** The paper states that the paraphrasing prompt included the CLC nomenclature and permitted semantically valid substitutions across hierarchy levels, giving the example of referring to *Urban fabric* (an L2 class) collectively as *Artificial surfaces* (an L1 class). So the question vocabulary spans the hierarchy.

The fix is not to pick a level. It is to **predict at L3 and aggregate at query time**, with the hierarchy as a first-class object in the geometry engine. The previous document has no hierarchical aggregation anywhere, and this is a genuine architectural gap, not a detail. Counting "how many artificial-surface regions" on an L3 map requires merging L3 siblings into one binary mask *before* running connected components — otherwise a city split into continuous and discontinuous urban fabric counts as two regions when the ground truth says one. Get this wrong and you lose the counting sub-task systematically.

### **F2 — The accuracy targets are asserted, not derived, and their ordering is wrong**

§28.2 sets targets of >85 counting, >85 adjacency, >80 area, >65.84 ref-exp. There is no derivation. The document elsewhere (correctly) proposes an oracle experiment to establish the ceiling — but then states targets *ahead of* running it. Those two things are in tension, and a SAC judge who reads carefully will spot it.

Worse, the implied ordering is wrong. Ranked by **robustness to segmentation error** — which is what actually determines post-segmentation accuracy — the symbolic operations are:

| Operation | Robustness | Why |
|---|---|---|
| **Area** | Highest | Integrates over thousands of pixels; independent per-pixel errors average out. A 5% pixel error rate produces well under 5% area error if errors are unbiased. |
| **Adjacency** | High | Dilation-and-intersect over large regions; needs only that both classes exist roughly in the right places. |
| **Relative position** | High | Centroids are averages; robust for the same reason as area. |
| **Presence** | Medium | Bounded directly by sibling confusion, which is what the benchmark's adversarial "no" answers target. |
| **Referring box** | Medium | Needs the *correct instance*, not just the correct class. Selection error is unforgiving. |
| **Counting** | **Lowest** | A single spurious 3-pixel blob changes the answer. A single thin misclassified bridge merges two regions into one. Counting has no averaging. |

The previous document groups counting with adjacency at >85. My PRIOR is the opposite: **counting will be the weakest symbolic sub-task, and area the strongest.** This matters because it changes where you spend week 5. The counting path needs a fitted post-processing pipeline (minimum mapping unit, morphological opening, hole filling), all of which should be tuned on ground-truth maps in week 2 and then re-tuned on *predicted* maps in week 5. That second tuning pass does not exist in the previous plan.

### **F3 — Binary VQA is treated as an exact comparison; it is actually a decision problem, and no model is assigned to it**

VERIFIED from §3.1: for count and size questions, "no" answers are constructed so that **the queried class is present but the stated quantity is wrong**. So answering "is there approximately 45,000 m² of coniferous forest?" is not `computed == stated`. It is: *given my estimate, my uncertainty, and the generator's near-miss distribution, is the stated value inside the acceptance region?*

That is a binary decision under uncertainty with an empirically-determined boundary. The previous document handles it as a data-mining task in §8.4 ("fit tolerance bands"), which is right in spirit, but it never appears in the architecture as a component with inputs, a loss, and a metric. **It should be an explicit trained model.** It is small, tabular, interpretable, and it is one of the "specialized models per task" the problem statement asks for. Specified as M3 in §3.3.

Critically, this model must be **trained on features computed from *predicted* maps, not ground-truth maps**, so that it learns to compensate for your segmenter's systematic biases. If your segmenter over-fragments forest, the model learns that your counts run high and shifts the boundary. That is a free accuracy gain and it is invisible to anyone who treats tolerance as a constant.

### **F4 — The MCQ metadata sub-tasks are dismissed, and they are 3 of 8 categories**

MCQ has eight sub-categories: presence, area, count, adjacency, relative position, **country, season, climate zone**. The last three are metadata-derived, not geometry-derived (VERIFIED: acquisition season, country and Köppen-Geiger zone are appended during caption generation from external maps, not inferred from pixels). The previous document says these are "worth a small classifier at most" and defers them pending an investigation of what metadata the harness supplies.

That is under-investing in three-eighths of an MCQ score. And the training data is free: reBEN carries country, season and geolocation for all 549,488 patches, and Köppen zone is a lookup from coordinates against a public 1 km climate map. This is a clean, cheap, supervised multi-task classification problem with a quarter-million labelled examples. **It deserves to be a first-class model.** Specified as M5 in §3.5.

Note also the published evidence that these are *learnable from pixels*: Qwen3-VL reaches 47.76% on country and 45.93% on climate zone as a 4-option MCQ against 25% chance (PUBLISHED, Table 4), with no task-specific training at all. A dedicated classifier trained on 229k patches should do considerably better. That is a real, defensible, low-risk gain the previous plan leaves on the floor.

### **F5 — Weight sharing between the segmenter and the VLM is elegance bought with accuracy**

§7.2 says: run both segmentation encoder options and, if the gap is under ~2 mIoU, take the frozen reBEN ViT for the weight sharing with the VLM path.

I disagree, and the reasoning is specific. The reBEN pretrained ViTs are `vit_base_patch8_224` checkpoints trained for **multi-label scene classification**. Using them for dense prediction means (a) upsampling 120×120 inputs to 224×224 to match the position embeddings, which fabricates resolution you do not have, and (b) decoding a 28×28 token grid back to 120×120, a 4.3× upsample against reference polygons you are trying to delineate. Classification pretraining also actively discards spatial precision — that is what global pooling is for.

Meanwhile the segmentation problem is **data-rich**: 229k labelled 120×120 patches for a 44-class dense problem. Pretraining matters most when labels are scarce. Here they are not.

**Recommendation: do not share.** Train the segmenter for segmentation. Use the frozen reBEN ViTs only in the VLM path, where the published recipe uses them and where comparability is the point. You lose a nice slide and you gain mIoU. The user asked me to prioritise accuracy over architectural neatness; this is where that trade appears concretely.

### **F6 — The Indian-data plan is the weakest section of the document, and it is built on a conflation**

§18.1 ranks "Indian open data fine-tuning (Bhoonidhi ≥5 m)" as **P2, medium benefit, unmeasurable**, and §30.4 lists it **first on the sacrifice order**. The reasoning is: we cannot get Cartosat-2S, so we cannot measure the gap, so effort here is unfalsifiable.

That reasoning conflates two independent domain shifts:

| Shift | What changes | Can we get data? |
|---|---|---|
| **Sensor shift** | 10 m → 0.65–2 m GSD; 10 bands → 4 bands; Sentinel-1 IW GRD → RISAT modes | **No.** Cartosat-2S is priced out. This part is genuinely unmeasurable. |
| **Geographic shift** | Indian phenology, monsoon cropping calendars, field sizes (fragmented smallholdings vs European consolidated parcels), settlement morphology, laterite/black-cotton soil spectra, different class prior | **Yes. Completely. For free.** |

Sentinel-1 and Sentinel-2 image India on the same schedule they image Europe, from the same sensors, through the same free Copernicus distribution. Pixel-level land cover labels over India are available at 10 m from ESA WorldCover (CC-BY) and Google Dynamic World, and at coarser scale from ISRO's own Bhuvan thematic services (LULC at 1:250,000 annually since 2005–06, at 1:50,000 for three epochs, and at 1:10,000 under SIS-DP).

So you can build an **Indian training and validation corpus with exactly the sensors, exactly the resolution, and exactly the patch geometry of your training data**, differing only in geography. It is measurable, it is free, and it isolates the one axis of the shift you can actually attack. The previous document's own §3.6 table lists "Geography: 10 European countries → India" as a distinct row and then never addresses it. This is the single largest missed opportunity in the plan. Full treatment in §5.

### **F7 — The strongest scientific argument for the architecture is never made**

The previous document defends the symbolic path on benchmark grounds: it wins on the sub-categories that are arithmetic. True, but there is a much stronger argument available, and it is the answer to the question you are most worried about.

**In a VLM-only design, the Indian domain gap is distributed across a model you can only adapt with Indian image–text pairs — and no such corpus exists.** There is no Indian BigEarthNet.txt. Nobody has built one. You cannot LoRA your way to India without Indian instruction data.

**In the segmentation-plus-symbolic design, the entire Indian gap is concentrated in exactly one model — the segmenter — which you can adapt with Indian pixel labels, which are free.** The geometry engine is sensor-agnostic and geography-agnostic by construction: `binary_dilation` does not care whether the built-up region is in Bavaria or Bengaluru. The answer grammar is a property of the annotation generator, not of the imagery.

That is the real argument. It is not "symbolic is more accurate on a European leaderboard". It is **"symbolic is the only one of the two designs that is adaptable to India at all, because it localises the entire domain shift into the one component for which Indian supervision exists."** Say that on stage.

### **F8 — No blind baseline, no significance testing, and the benchmark split is small**

Two methodological gaps that a scientific judge will find.

**Blind baselines.** VQA benchmarks are notorious for answerable-without-the-image questions, and CDVQA specifically has documented language-bias problems. You must report:
- a **question-only baseline** (answer from the question text alone, no image),
- a **majority-class baseline** per sub-category,
- a **class-prior baseline** (answer from the marginal LULC class distribution).

If your system does not clearly beat these, the benchmark is measuring priors, not perception. Reporting them is cheap and it is the mark of someone who has done this before. The previous document has seven ablations and none of them is a blind baseline.

**Significance.** The benchmark split is 1,082 image pairs and 15,029 annotations (VERIFIED): 6,927 binary VQA, 5,550 MCQ, 970 captions, 1,582 referring-expression. Split across sub-categories that is roughly 1,700 binary annotations and 700 MCQ annotations per sub-task. At p≈0.7 with n=1,700, the 95% confidence interval is about **±2.2 points**. At p≈0.5 with n≈700, it is about **±3.7 points**.

So: **differences under ~3 points on binary sub-tasks and under ~4 points on MCQ sub-tasks are not distinguishable from noise on this split.** That has direct consequences:
- Do not hill-climb on differences that small. You will be fitting noise.
- Report bootstrap confidence intervals on every headline number.
- Use **McNemar's test** for paired comparisons (symbolic vs VLM on identical questions) — it is the correct test when both systems answer the same items and it is far more powerful than comparing two independent proportions.
- The §12.1 tie-break rule "if the gap is under ~2 mIoU" is, on this split, a rule for choosing between two indistinguishable options. Fine as a tie-break; do not present it as a measured result.

### **F9 — The scope is too large for 6 students in 8 weeks**

§1.3 scores sixteen components. §27.3 budgets ~48 person-weeks. §26 also budgets a per-member learning plan, implying several of the six are learning remote sensing from scratch. The plan additionally includes a React + MapLibre frontend, a PostGIS-backed trace store, a WeasyPrint PDF generator, Docker Compose deployment, a licence audit, and seven ablation studies.

That is not a six-student eight-week project. It is a small lab's quarter.

I am not going to soften this. **The single highest-probability failure mode for this project is not a wrong architectural choice — it is arriving at week 7 with six half-built components and no measured numbers.** My recommended architecture in §2 is deliberately *smaller* than the one under review. Specific cuts in §7.4.

### **F10 — The 0.5B LLM fallback for query classification is unnecessary complexity**

§C3 proposes: rules first, then a local 0.5B model scoring 8 task labels by likelihood if the rules fail. That is a GPU-resident model, a loading cost, a latency cost, and an unbounded failure surface, for an 8-way closed classification over a vocabulary you control.

**Replace it with a TF-IDF + linear SVM, or a fine-tuned MiniLM sentence classifier (~22M params, CPU-only).** You can generate 20–50k training queries by permuting the benchmark's own templates, which you already plan to extract in week 1. This trains in seconds, runs on CPU, is fully auditable, and will hit the 98%+ target the document sets. It also removes a GPU dependency from the request path.

### **F11 — Spatial leakage risk is acknowledged but not operationalised**

reBEN provides a geographic split, and the document correctly says to carve a validation split out of train because the reference model trained on train+val. But it does not say **how** to carve it. If you carve randomly, you leak: adjacent 1.2 km patches are strongly spatially autocorrelated, and a random split puts near-duplicate patches on both sides. Your validation mIoU will be optimistic by several points and you will make wrong decisions with it.

**Carve the internal validation split by geographic block** — by country, or by a coarse spatial grid, or by reBEN's own S2 tile identifiers. Say so in the methodology. This is a standard geospatial ML pitfall and getting it right is a credibility marker.

### **F12 — Confidence has three signals but no fitted model**

§17 proposes class margin, TTA component stability, and area interval as three confidence signals, then temperature calibration. What is missing is the combining function. Three signals plus a threshold is not a calibrated confidence; it is three thresholds.

**Fit a single logistic regression from those features to P(answer is correct)**, on a held-out calibration split, and report ECE, Brier score, and a risk–coverage curve. That is a five-line model, it is interpretable (you can print the coefficients on a slide), and it turns "confidence" from a claim into a measured quantity. Specified as M9.

## 1.3 What the previous document gets right and should not be changed

For balance, because a review that only lists faults is not a useful review:

- **The core symbolic insight.** Verified correct against the paper's generation pipeline. This is the whole project.
- **Deterministic router over an LLM planner.** The problem statement's language about a predefined registry and permitted parameters is pointing directly at this. An LLM planner adds a hallucination surface for zero scored gain, and the trace is explicitly what gets evaluated.
- **Constrained decoding and likelihood scoring instead of free generation.** PUBLISHED evidence that multiple evaluated models fail instruction-following on multiple task categories, and that the paper's authors extracted answers generously even when format was violated. Fixing this is cheap and it is free score.
- **The oracle experiment** (symbolic engine on ground-truth maps). This is the most valuable single experiment in the plan. It separates "the idea is wrong" from "the segmentation is not good enough yet", and almost nobody runs it.
- **The connectivity/MMU fitting experiment (A7).** Recovering the generator's exact conventions from the released answers is free accuracy and it is invisible to anyone treating the dataset as a black box.
- **The two operating modes** (abstain in operation, never abstain when scored). Correct, and the observation that abstention on a scored leaderboard is a wrong answer is one that costs teams real points every year.
- **Refusing to fabricate Cartosat/RISAT numbers.** Keep this discipline. It is worth more than a confident guess.
- **The input validator.** An explicit requirement that most teams will skip, and ten seconds of demo that demonstrates compliance.

## 1.4 Is there a fundamentally better architecture?

I looked for one. I do not think there is, and here is the reasoning rather than the assertion.

The space of designs is essentially:

1. **Monolithic VLM, fine-tuned per task.** This is the published reference (RS-InternVL: 34.04 / 73.29 / 51.49 / 65.84 across captioning, binary VQA, MCQ, ref-exp — PUBLISHED, Table 8). It is a fair, credible target. But those numbers came from four-plus separately fine-tuned adapters trained on train+val for one epoch at roughly two days on four H200s. You cannot reproduce that on a 4090, and even if you could, matching a published baseline is not a differentiator when the paper is linked from the problem statement.

2. **Predict a map, compute the answer.** Structurally aligned with how the ground truth was made. Cheap to train. Auditable. Concentrates the domain gap into one adaptable component.

3. **Neuro-symbolic with a learned program synthesiser** (LLM emits a program over geometric primitives, program executes). More flexible than a fixed registry, and genuinely more novel. But: the task vocabulary is closed at 15 tasks, so there is nothing for the synthesiser to generalise to; it adds an unbounded failure mode; and it is directly contrary to the problem statement's "predefined registry / only permitted parameters" language. **Rejected — novelty that costs compliance and gains no score.**

4. **End-to-end dense-prediction VQA** (a single network that takes image + question and outputs an answer, with the map as an auxiliary head). Attractive in principle — it could learn to compensate for segmentation error in the answer head. In practice it destroys auditability, which is a stated requirement, and it needs far more compute to train than option 2. **Rejected, but worth mentioning on stage as a considered alternative.**

Option 2 wins. **My recommendation is therefore a restructured and substantially trimmed version of the architecture under review, not a replacement.** I want to be straightforward about that rather than manufacturing disagreement: the previous document's central judgement was right. What it needs is the taxonomy fixed, four missing models specified, six components deleted, and a real Indian evaluation track.

---

# 2. The final architecture

## 2.1 One-paragraph statement

One multi-sensor dense-prediction model predicts a CORINE Level-3 (44-class) land-cover map from co-registered Sentinel-1 and Sentinel-2 input. A hierarchy-aware symbolic geometry engine aggregates that map to whatever CLC level the question asks about and computes presence, count, area, adjacency, relative position and referring boxes exactly. Three small tabular decision heads convert those computed quantities into the benchmark's answer formats (binary yes/no under a fitted tolerance, MCQ option selection, calibrated confidence). One image classifier handles the three metadata MCQ sub-tasks that are not geometric. A separate Siamese semantic-change model produces a from-to transition matrix for the bi-temporal path, over which change answers are again computed. A single LoRA-adapted InternVL3-1B handles free-form language and captioning, and serves as the fallback when the symbolic path is uncertain. Everything runs locally, emits a structured trace, and reports calibrated confidence. **The entire Indian domain gap is concentrated in the segmenter and the change model — the two components for which Indian pixel supervision is obtainable.**

## 2.2 The pipeline, stage by stage

```
                              ┌──────────────────────────────────┐
  INPUT                       │  1–2 GeoTIFFs  +  text query      │
                              └────────────────┬─────────────────┘
                                               │
  ═══════════════════════════════ STAGE 1 — VALIDATION ═════════════════════════════
                              ┌────────────────▼─────────────────┐
                              │ V1  INPUT VALIDATOR   (rasterio)  │
                              │ band count · dtype · CRS ·        │
                              │ geotransform · shape · nodata ·   │
                              │ modality inference ·              │
                              │ pair co-registration check ·      │
                              │ metadata string sanitisation      │
                              │        → InputManifest            │
                              │        → or typed rejection       │
                              └────────────────┬─────────────────┘
                                               │
  ═══════════════════════════ STAGE 2 — PREPROCESSING ══════════════════════════════
                              ┌────────────────▼─────────────────┐
                              │ P1  SENSOR NORMALISATION          │
                              │ S1: linear→dB, per-band z-score   │
                              │     using TRAIN statistics        │
                              │ S2: 20m bands bilinear→10m,       │
                              │     per-band z-score, 60m dropped │
                              │ band-presence mask vector [10]    │
                              │ optional index channels           │
                              │     NDVI · NDWI · NDBI            │
                              └────────────────┬─────────────────┘
                                               │
  ═══════════════════════════ STAGE 3 — QUERY UNDERSTANDING ════════════════════════
       ┌───────────────────────────────────────▼─────────────────┐
       │ Q1  INTENT + ARGUMENT PARSER                             │
       │  rules over closed template set                          │
       │    → fallback: M10 TF-IDF + linear SVM (CPU, 8-way)      │
       │  CLC synonym table → class IDs AT ANY HIERARCHY LEVEL    │
       │  qualifier extraction (largest / north-of / …)           │
       │    → (intent, class_a@level, class_b@level, qualifier)   │
       └───────────────────────────────────────┬─────────────────┘
                                               │
  ═══════════════════════════ STAGE 4 — ROUTING ════════════════════════════════════
       ┌───────────────────────────────────────▼─────────────────┐
       │ R1  DETERMINISTIC ROUTER + FROZEN TOOL REGISTRY          │
       │  lookup: (intent × input_config) → ordered tool plan     │
       │  parameters bound + validated against Pydantic bounds    │
       │  no dynamic dispatch · no eval · no plugin loading       │
       │        → execution plan + trace header                   │
       └───────────────────────────────────────┬─────────────────┘
                                               │
  ═══════════════════════════ STAGE 5 — PERCEPTION (the learned layer) ═════════════
                              ┌────────────────▼─────────────────┐
                              │ SCENE CACHE (content hash + model│
                              │ version). Map computed ONCE per   │
                              │ scene, serves unlimited queries.  │
                              └────────────────┬─────────────────┘
                                        miss   │   hit ──────────────┐
              ┌──────────────────────────┬─────┴──────────┐          │
              │                          │                │          │
   ┌──────────▼──────────┐  ┌────────────▼──────────┐  ┌──▼──────────▼──────┐
   │ M1  MULTI-SENSOR    │  │ M5  SCENE METADATA    │  │ M6  SIAMESE        │
   │     LULC SEGMENTER  │  │     CLASSIFIER        │  │  SEMANTIC CHANGE   │
   │ dual encoder U-Net  │  │ ConvNeXt-Tiny, 12-ch  │  │ shared encoder     │
   │ S1[2] ‖ S2[10]      │  │ 3 heads:              │  │ T1,T2 → M1_t1,M1_t2│
   │ gated fusion @ skips│  │  country · season ·   │  │      + change mask │
   │ → logits[44,120,120]│  │  Köppen zone          │  │ → 6-class semantic │
   │ + 8× TTA            │  │ → 3 posteriors        │  │   maps both dates  │
   └──────────┬──────────┘  └────────────┬──────────┘  └──────────┬─────────┘
              │                          │                        │
              │                          │             ┌──────────▼─────────┐
              │                          │             │ FROM-TO TRANSITION │
              │                          │             │ MATRIX T[i][j]     │
              │                          │             │ under change mask  │
              │                          │             └──────────┬─────────┘
              │                          │                        │
  ═══════════ STAGE 6 — SYMBOLIC COMPUTATION (no learning, exact) ══════════════════
   ┌──────────▼──────────────────────────────────────────────────▼─────────┐
   │ S1  HIERARCHY-AWARE GEOMETRY ENGINE                                    │
   │                                                                        │
   │   step 0  AGGREGATE  L3(44) → requested CLC level via taxonomy YAML    │
   │           ← THE STEP THE PREVIOUS ARCHITECTURE WAS MISSING             │
   │   step 1  binary mask for the aggregated class                         │
   │   step 2  morphological cleanup (opening, hole fill) — params FITTED   │
   │   step 3  connected components (connectivity FITTED: 4 vs 8)           │
   │   step 4  drop components below fitted minimum mapping unit            │
   │   step 5  regionprops → per-instance area, bbox, centroid, fill ratio  │
   │                                                                        │
   │   presence   = |components| > 0                                        │
   │   count      = |components|                                            │
   │   area       = Σ pixels × GSD² , rounded to nearest 1000 m²            │
   │   adjacency  = binary_dilation(A, k) ∩ B  ≠ ∅   (k FITTED)             │
   │   rel. pos.  = sign of centroid delta, 8-way compass                   │
   │   ref-box    = filter{1%≤area≤50% AND bbox_fill≥40%} → argmax/argmin   │
   │   ref-point  = bbox of the component containing the given point        │
   │   tier       = primary >25% · secondary 5–25% · marginal <5%           │
   │   change     = queries over T (counts, argmax transitions, deltas)     │
   └──────────┬──────────────────────────────────┬──────────────────────────┘
              │                                  │
  ═══════════ STAGE 7 — ANSWER-FORMAT DECISION HEADS (small, fitted) ═══════════════
   ┌──────────▼─────────┐  ┌───────────▼────────┐  ┌────────────────────────┐
   │ M3 BINARY DECISION │  │ M4 MCQ OPTION      │  │ M7 VLM  InternVL3-1B   │
   │ LightGBM / logistic│  │    SCORER          │  │  + S1/S2 branches      │
   │ features:          │  │ distance in FITTED │  │  + LoRA r8 α32 d0.1    │
   │  computed value    │  │ metric between     │  │  ONLY for:             │
   │  stated value      │  │ computed value and │  │   · free-form text     │
   │  log ratio         │  │ each option        │  │   · captioning (if the │
   │  class margin      │  │ + M5 posteriors    │  │     H-CAP path fails)  │
   │  TTA count σ       │  │   for Loc/S/Clt    │  │   · fallback when      │
   │  question subtype  │  │ → argmax option    │  │     confidence is low  │
   │ → P(yes)           │  │                    │  │  constrained decoding  │
   └──────────┬─────────┘  └───────────┬────────┘  └────────────┬───────────┘
              │                        │                        │
  ═══════════ STAGE 8 — CONFIDENCE ════════════════════════════════════════════════
   ┌──────────▼────────────────────────▼────────────────────────▼───────────┐
   │ M9  CALIBRATOR — logistic regression → P(answer correct)                │
   │   inputs: mean class margin inside components · TTA stability ·         │
   │           area interval width · component-count σ · band-presence ·     │
   │           sibling-confusion prior for the queried class                 │
   │   fitted on a held-out calibration split · isotonic post-hoc            │
   │   reports: ECE · Brier · risk–coverage curve                            │
   └──────────┬─────────────────────────────────────────────────────────────┘
              │
   ┌──────────▼─────────────────────────────────────────────────────────────┐
   │ ABSTENTION POLICY   (single config flag, two modes)                     │
   │   operational : below τ → abstain, name the class and the reason        │
   │   benchmark   : NEVER abstain → symbolic → VLM → class prior → majority │
   └──────────┬─────────────────────────────────────────────────────────────┘
              │
  ═══════════ STAGE 9 — ASSEMBLY AND EVIDENCE ═════════════════════════════════════
   ┌──────────▼─────────────────────────────────────────────────────────────┐
   │ A1  ANSWER ASSEMBLER                                                    │
   │   HARD RULE: the number comes from the geometry engine. A language      │
   │   model may phrase an answer; it may never produce the number in it.    │
   │   (optional) M8 template→style rewriter for caption surface form        │
   └──┬──────────────────┬──────────────────┬──────────────────┬────────────┘
      │                  │                  │                  │
 ┌────▼─────┐    ┌───────▼────────┐  ┌──────▼───────┐  ┌───────▼────────┐
 │ EVIDENCE │    │ EXECUTION      │  │ PDF REPORT   │  │ STRUCTURED     │
 │ overlay  │    │ TRACE          │  │ query·inputs·│  │ JSON RESPONSE  │
 │ numbered │    │ task·tools·    │  │ map·arith·   │  │ value·unit·    │
 │ components│   │ params·timings·│  │ confidence·  │  │ confidence·    │
 │ boxes    │    │ model hash     │  │ attributions │  │ evidence refs  │
 │ heatmap  │    │ → append-only  │  │              │  │                │
 └──────────┘    └────────────────┘  └──────────────┘  └────────────────┘
```

## 2.3 How the specialised models interact

The interaction pattern is deliberately **hierarchical, not peer-to-peer**. Models do not talk to each other; they write into a shared, typed scene representation that the symbolic engine reads. This is what makes the trace meaningful and the failure modes diagnosable.

**The contract between components:**

| From | To | What passes | Type |
|---|---|---|---|
| M1 | Geometry engine | `logits[44,120,120]` + `argmax_map[120,120]` | tensor + int array |
| M1 | M9 calibrator | per-pixel class margin, TTA variance | float arrays |
| M5 | M4 | posteriors over country / season / climate | 3 probability vectors |
| M6 | Geometry engine | `map_t1[6,H,W]`, `map_t2[6,H,W]`, `change_mask[H,W]` | tensors |
| Geometry engine | M3 / M4 | computed scalar + per-instance properties | typed struct |
| Geometry engine | M7 | caption attribute struct (classes, tiers, sizes, adjacencies) | JSON |
| M3 / M4 | M9 | decision + margin | float |
| M9 | Assembler | `P(correct)` + band | float + enum |

**Three interaction rules that are non-negotiable:**

1. **No model consumes another model's natural-language output.** M7 receives a structured attribute dictionary from the geometry engine, never a sentence from another component. This eliminates a whole class of compounding-error failures.
2. **Numbers flow one way.** The geometry engine is the only producer of quantities. M3, M4, M7 and the assembler are consumers. If you ever find yourself parsing a number back out of generated text, you have introduced a bug.
3. **The scene cache is keyed on `hash(scene_bytes) + model_version`.** A map produced by a different checkpoint is never served. This is both correctness and a reproducibility property you can point at.

**The fallback chain**, which is where the models genuinely interact:

```
query → symbolic path
          │
          ├─ M9 says P(correct) ≥ τ_high  ────────────→ answer, high confidence
          │
          ├─ τ_low ≤ P(correct) < τ_high  ────────────→ answer + explicit uncertainty band
          │
          └─ P(correct) < τ_low
                     │
                     ├─ operational mode ─────────────→ abstain, name the failing class
                     │
                     └─ benchmark mode ───────────────→ M7 VLM answer
                                                          │ if unparseable
                                                          └→ class-prior answer
                                                               │ if no prior
                                                               └→ majority answer
```

Report how often each rung fires. A judge who sees that you measured your own fallback rate trusts the rest of your numbers.

---

# 3. Every model, specified explicitly

A note before the specifications. For most of these components **there is no published accuracy for our exact setup**, because nobody has published a symbolic-geometry system on this benchmark — the benchmark is months old and the only published fine-tuned baseline is RS-InternVL. Where that is the case I say so, give a PRIOR with the reasoning that produced it, and name the experiment that replaces the guess with a measurement. Do not put my PRIORs on a slide. Put your measurements on a slide.

---

## 3.1 M1 — Multi-sensor LULC semantic segmentation

**Task:** dense pixel classification of a co-registered S1+S2 patch into CORINE Level-3 land-cover classes.

**Model:** **Dual-encoder U-Net with gated fusion at every skip level.**
- Encoders: `ConvNeXt-V2-Tiny` (or `ResNet-34` if you want speed) from `timm`, via `segmentation_models_pytorch`. Two independent encoders — S1 (2 channels) and S2 (10 channels, plus 3 optional index channels).
- Fusion: per-level concatenation → 1×1 conv → squeeze-and-excite channel gate. Cheap, and the gate weights are directly readable as modality attribution.
- Decoder: standard U-Net decoder to full 120×120 resolution, skips from both encoders.
- Head: 1×1 conv → **44 classes** (CLC Level-3), plus an auxiliary 19-class head and an auxiliary coarse-7 head (see loss).
- Params: ~30–45M.

**Concrete starting point:**
```python
import segmentation_models_pytorch as smp
# baseline to beat, single-encoder early fusion:
model = smp.Unet(encoder_name="tu-convnext_tiny", encoder_weights=None,
                 in_channels=12, classes=44, decoder_attention_type="scse")
```
Then implement the dual-encoder variant and compare. **Run early fusion as the ablation baseline** — if it matches the dual encoder, you have saved yourself a component, and that is a finding worth reporting.

**Why this model and not the alternatives:**

| Alternative | Why rejected |
|---|---|
| Frozen reBEN ViT-B/8 + UPerNet | Classification-pretrained, needs 120→224 upsampling to match position embeddings, decodes a 28×28 grid back to 120×120. Pretraining pays off in low-data regimes; 229k labelled patches is not one. See F5. |
| SegFormer-B0 | Genuinely competitive and 8× smaller. **Worth running as candidate two.** Attention at 120×120 is cheap. My PRIOR is that it lands within noise of the U-Net; if it does, take it for the deployment story. |
| Mask2Former / SAM-style | Instance-query architectures are built for large, cluttered scenes with crisp object boundaries. CORINE polygons at 25 ha MMU on a 1.2 km patch are neither. Over-engineered; rejected. |
| DeepLabv3+ | Fine, no advantage. ASPP's dilated context is designed for large receptive fields on large images. |

**Input features:**
- S1: VV, VH in dB, per-band standardised with **training-split statistics only** (never per-image, never per-batch — that leaks and it breaks at inference on single images).
- S2: B02, B03, B04, B05, B06, B07, B08, B8A, B11, B12. The four 10 m bands native; the six 20 m bands bilinearly upsampled to 10 m. **60 m bands discarded** — the reference recipe discards them and the paper's justification (atmospheric correction and cloud screening, limited semantic content) is sound.
- Optional derived channels: NDVI, NDWI, NDBI. These are redundant for a large model given the raw bands, but they help materially **under band dropout**, because an index computed from surviving bands carries information a zeroed band cannot. Cheap; ablate it.
- A **band-presence mask** `[10]` broadcast as a learned embedding, so the network can distinguish a dropped band from a genuinely dark one. Without this, band dropout teaches the model that zeros mean "very low reflectance", which is exactly wrong.

**Output:** `logits[44, 120, 120]`, plus `argmax_map`, plus per-pixel top-1 margin.

**Loss:**
```
L = L_ce  +  0.5 · L_lovasz  +  0.3 · L_hier  +  0.2 · L_scale_consistency

L_ce     : cross-entropy, ignore_index = unclassified,
           class weights = inverse-sqrt frequency, capped at 5×
L_lovasz : Lovász-Softmax — directly optimises the IoU surrogate,
           which is what you are scored on, and it handles rare classes
           better than Dice at this class count
L_hier   : hierarchy-aware penalty. Confusions that cross a CLC Level-1
           branch (e.g. Artificial ↔ Forest) weighted 1.5×; confusions
           within a Level-3 sibling group weighted 1.0×.
           RATIONALE (VERIFIED): the benchmark's "no" answers for presence
           and adjacency are built from semantically similar classes in the
           CLC hierarchy. Sibling confusion is what the test set punishes,
           so make the loss reflect the evaluation.
L_scale  : consistency loss — resample input to a random factor in
           [0.5×, 4×], predict, resample prediction back, penalise KL
           divergence against the native-scale prediction.
           This is the GSD-gap defence and it is also a measurable
           robustness curve. See §5.
```

**Evaluation metrics:**
- Primary decision metric: **downstream symbolic accuracy** (compute presence/count/area/adjacency from the predicted map, score against released annotations). This is what is scored; optimise it.
- Reported: mIoU at L3-44, mIoU aggregated to 19-class, mIoU aggregated to coarse-7, per-class IoU (full table — the mean hides the classes that matter), overall pixel accuracy.
- Diagnostic: 44×44 confusion matrix with CLC sibling groups highlighted.
- Robustness: mIoU under each of the seven perturbations in §5.4.

**Training regime: TRAIN FROM SCRATCH** (encoder randomly initialised, or ImageNet-initialised on the RGB channels only with the rest random).

Justification, since this contradicts reflexive practice: 229,114 labelled training patches for a dense-prediction task on 120×120 images is a **data-rich regime**. ImageNet or reBEN-classification pretraining buys you a prior you can learn directly from this much supervision, and it costs you an input-format mismatch (3 channels vs 12) and a spatial-precision loss. Run ImageNet-init as an ablation; my PRIOR is that it converges faster and finishes within noise.

**Realistic expected performance:**

> **There is no published mIoU baseline for CLC Level-3 dense segmentation on reBEN that I could verify.** reBEN's own paper and the community's use of it centre on multi-label classification. Anyone who quotes you a number for this is guessing.

PRIOR, with reasoning: CORINE polygons are generalised at a 25 ha minimum mapping unit and were photo-interpreted at 1:100,000 scale, then rasterised to 10 m. That means the *labels themselves* disagree with the pixels near every boundary — there is an irreducible label-noise ceiling well below 100%. Combine that with 44 classes on a 1.2 km patch, most of which contain 2–5 classes, and a long tail of classes appearing in well under 0.1% of patches:

| Level | PRIOR mIoU range | Confidence in the prior |
|---|---|---|
| L3, 44 classes, all classes in the mean | **30–50** | Moderate. Dragged down hard by the tail. |
| L3, 44 classes, restricted to classes with ≥0.5% pixel share | 45–65 | Moderate |
| Aggregated to 19 classes | **55–70** | Moderate |
| Aggregated to coarse-7 (built-up / crop / tree / grass-shrub / water / bare / wetland) | **75–88** | Higher — this is the level at which cross-taxonomy comparison works |
| Overall pixel accuracy, L3 | 70–85 | Higher — dominated by the few frequent classes |

**Measure this in week 3 and replace the table.** If your L3 mIoU lands below ~25, something is wrong with the label loading, not with the model.

---

## 3.2 M2 — Symbolic geometry engine (deterministic, not learned)

Included here because the user asked for every component, and because its *parameters* are fitted even though its logic is not.

**Task:** convert a predicted class map into exact answers for presence, count, area, adjacency, relative position, referring box, referring point, and caption attributes.

**Algorithm:** `scipy.ndimage` + `skimage.measure`. Specifically: `label` (connected components), `binary_dilation`, `binary_opening`, `binary_fill_holes`, `regionprops`.

**The fitted parameters** — these are the accuracy-relevant part, and fitting them is the cheapest points in the project:

| Parameter | Fit against | Why it matters |
|---|---|---|
| Connectivity (4 vs 8) | Ground-truth maps → released counts | Swings **every** counting answer. One afternoon of work. |
| Minimum mapping unit (pixels) | Same | Determines whether a 3-pixel speck counts as a region |
| Morphological opening kernel | Same | Removes thin false connections that merge two regions into one |
| Adjacency dilation radius | Ground-truth maps → released adjacency answers | Is "adjacent" touching, or within k pixels? |
| Area rounding | Known: nearest 1000 m² (VERIFIED) | Confirmed, no fitting needed |
| Hierarchy aggregation table | CLC nomenclature | **The missing piece** — see F1 |

**Fit procedure:** sweep each parameter, computing answers from *ground-truth* reference maps, and select the setting that reproduces the released annotations most exactly. If a setting reproduces them at 100%, you have recovered the generator's convention and that is free accuracy for the rest of the project. **Then re-fit the MMU and opening kernel a second time against *predicted* maps in week 5**, because the optimal cleanup for a noisy map is not the optimal cleanup for a clean one. The previous plan does the first fit and not the second.

**Metrics:** exact-match rate against released annotations, computed on ground-truth maps (the oracle). Target: ≥99% on presence, area, adjacency, relative position. If the oracle is not near-perfect, you have not recovered the conventions and no amount of segmentation quality will save you.

**Testing:** property-based tests (Hypothesis) on synthetic maps with known component structure, plus a golden-file suite.

---

## 3.3 M3 — Binary VQA decision head

**Task:** given a computed quantity, a stated quantity, and uncertainty signals, decide yes/no.

**Model:** **LightGBM binary classifier** (~200 trees, depth 4), or L2-regularised logistic regression if you want maximum interpretability. Not a neural network — this is a tabular problem with a few thousand training examples and a low-dimensional feature space.

**Why:** VERIFIED that "no" answers for count and size questions are constructed so the queried class is present but the stated quantity is wrong. The decision boundary is therefore an empirical property of the annotation generator's near-miss sampling, not a physical constant. A tabular model fits it from data, is fully auditable (you can print the decision path in the trace), trains in seconds, and — critically — **learns to compensate for your segmenter's systematic biases** because it is trained on features from predicted maps.

**Input features:**
```
computed_value          float   from the geometry engine
stated_value            float   parsed from the question
abs_diff                float
log_ratio               float   log(computed / stated), the right scale for areas
rank_diff               int     for counts: computed − stated
question_subtype        cat     {presence, area, count, adjacency}
class_id                cat     the queried CLC class
class_pixel_share       float   how much of the scene the class occupies
mean_class_margin       float   segmenter confidence inside the components
tta_count_std           float   how much the count moves across 8 TTA transforms
n_components_near_mmu   int     components within 10% of the MMU threshold
sibling_confusion_prior float   from the 44×44 confusion matrix
```

**Output:** `P(yes)`.

**Loss:** binary cross-entropy (log loss). Class-balanced — the benchmark split is balanced across answer options (VERIFIED), so balance your training set to match or the calibration will be off.

**Evaluation metrics:** accuracy per sub-type (presence / area / count / adjacency) to match the paper's Table 3 layout; ROC-AUC; **Expected Calibration Error** (this model's probability feeds M9); McNemar's test against a hard-threshold baseline.

**Training regime: TRAIN FROM SCRATCH** on the BigEarthNet.txt train split, with features computed from **predicted** maps produced by the frozen M1 checkpoint. Roughly 100k–500k training examples available; you need far fewer. Hold out a calibration split.

**Realistic expected performance:** No published comparison exists. PRIOR: this model should beat a hand-tuned fixed threshold by a few points on count and area, and should be near-lossless on presence and adjacency (where the decision is essentially exact and the model just needs to not get in the way). The binding constraint is the accuracy of `computed_value`, not the decision head. **Expected AUC 0.75–0.92 depending on sub-type**, with area highest and count lowest — mirroring the robustness ordering in F2.

---

## 3.4 M4 — MCQ option scorer

**Task:** select one of four options given a computed quantity (geometric sub-tasks) or a classifier posterior (metadata sub-tasks).

**Model:** two paths, routed by sub-category.
- **Geometric (Pr, A, Cnt, Adj, RP):** distance-based selection in a **fitted metric**. Not naive absolute distance — for areas the right scale is log, for counts it is rank. Fit the scale on the train split by maximising option-selection accuracy. Formally a 4-way softmax over `−d(computed, option_k)/T`, with `d` and `T` fitted.
- **Metadata (Loc, S, Clt):** argmax of M5's posterior restricted to the four offered options.

**Why:** VERIFIED that each MCQ has one correct answer and three distractors "sampled by analogous principles to the binary VQAs" — i.e. near-misses. That means distractor spacing is a fittable property. If area distractors sit at roughly ±30%, your area estimate only needs to be within ~15% to snap correctly, which is a much weaker requirement than exactness. **Quantify the distractor spacing in week 1 from the parquet** — it tells you precisely how accurate M1 needs to be, and that is a design input, not a post-hoc observation.

**Input features:** computed value; the four option values (parsed); sub-category; M5 posteriors where applicable; the same uncertainty signals as M3.

**Output:** argmax option index, plus a softmax distribution for calibration.

**Loss:** 4-way cross-entropy over options.

**Evaluation metrics:** accuracy per sub-task (Pr, A, Cnt, Adj, RP, Loc, S, Clt, overall) to match Table 4; instruction-following rate (should be 100% by construction — you select, you never generate).

**Training regime: FIT the metric parameters** on the train split. Only a handful of parameters; not a training run.

**Realistic expected performance:** PRIOR: on the five geometric sub-tasks, substantially above the published RS-InternVL MCQ overall of 51.49, because selection among four spaced options is a far weaker requirement than exact computation. On the three metadata sub-tasks, bounded entirely by M5. **The honest headline: MCQ overall is a weighted average across eight sub-tasks, three of which we cannot solve geometrically. Do not promise an overall number until M5 is measured.**

---

## 3.5 M5 — Scene metadata classifier (country / season / climate zone)

**Task:** predict acquisition country, acquisition season, and Köppen-Geiger climate zone from the image patch.

**Model:** **ConvNeXt-Tiny** (or ResNet-50) with a 12-channel stem and three linear heads. ~28M params. ImageNet-initialised on the RGB channels, remaining channels randomly initialised (channel inflation).

**Why this is a real model and not an afterthought:** these are three of eight MCQ sub-categories. VERIFIED that season, country and Köppen zone were appended from external metadata during caption generation — they are not derivable from geometry, so the symbolic path cannot touch them. But they are learnable from pixels: PUBLISHED, a general-purpose VLM with no task training reaches 47.76% on country and 45.93% on climate zone against 25% chance (Table 4). A dedicated classifier with 229k in-domain training patches should do considerably better. And the labels are **free** — reBEN carries country, acquisition date and geolocation for every patch; Köppen zone is a coordinate lookup against a public 1 km climate raster.

**Input features:** S2 10 bands + S1 2 bands, same normalisation as M1. Plus, **if and only if the evaluation harness supplies it**, geolocation and acquisition date as auxiliary inputs — in which case country/season/climate become lookups and this model becomes unnecessary for scoring. **NEEDS CONFIRMATION in week 1: inspect the parquet and determine what metadata rides along with each annotation.** This single check decides whether M5 is a P1 model or a discard.

**Output:** three posteriors — country (10-way, the reBEN countries), season (4-way), Köppen zone (k-way, k determined by what appears in reBEN).

**Loss:** sum of three cross-entropies, equally weighted, class-balanced per head.

**Evaluation metrics:** top-1 accuracy per attribute; and the derived metric that matters, **4-option MCQ accuracy** (restrict the posterior to the offered options and take argmax — this is much higher than top-1 over the full label set, and it is what gets scored).

**Training regime: TRANSFER LEARN** — ImageNet-initialised, fine-tune end to end. Cheap: a few GPU-hours.

**Realistic expected performance:** PRIOR, with reasoning per attribute:
- **Climate zone**: most learnable. Köppen zones are defined by temperature and precipitation regimes, which express strongly in vegetation type and phenology, which is exactly what multispectral imagery measures. Expect the highest of the three.
- **Season**: moderately learnable. Vegetation phenology and sun angle both carry signal, but a mid-latitude evergreen forest looks similar in spring and autumn. Expect moderate.
- **Country**: hardest. Ten European countries, some adjacent and agriculturally similar. Field geometry and settlement morphology carry real signal (Dutch polders do not look like Portuguese hills) but neighbouring countries will confuse.

I am not going to put numbers on those. **Train it in week 4 — it is a few hours — and measure.** The published zero-shot VLM numbers give you a floor to beat, which is the useful comparison.

---

## 3.6 M6 — Siamese semantic change model

**Task:** from a bi-temporal RGB pair, predict semantic land-cover maps for both dates plus a binary change mask, from which a from-to transition matrix is computed.

**Model:** **Siamese U-Net with a shared ImageNet-pretrained encoder and three heads.**
- Encoder: `ResNet-34` or `ConvNeXt-Tiny`, ImageNet-pretrained, **weights shared between the two dates** (this is what makes it Siamese and it is essential — independent encoders would learn date-specific features and fabricate change).
- Heads: `semantic_t1` (6-class SECOND taxonomy, shared weights with `semantic_t2`), `change` (binary, from `concat[f1, f2, |f1−f2|]`).
- Reference implementations worth reading before you write your own: **Bi-SRNet** and **SCanNet** (Ding et al.) are the standard published semantic-change architectures on SECOND. Look up their current reported SeK and mIoU rather than trusting a number from me — I did not verify them in this session.

**Why:** the transition matrix needs semantic maps for *both* dates, which binary change models (BIT, ChangeFormer) do not provide. And VERIFIED: CDVQA was auto-generated from SECOND's pixel-level semantic change maps over six classes, with answers in a closed set of 19 categories. So change VQA is arithmetic over the transition matrix, exactly as the main path is arithmetic over the LULC map. Same architecture family, same loaders, same harness, same auditability.

**Input features:** T1 and T2 RGB, 512×512 (SECOND's native size). Same geometric augmentation applied to **both** dates; photometric jitter applied **independently** per date (to simulate illumination and seasonal change); random 0–2 px shift of T2 (to simulate co-registration error); per-date standardisation so a global brightness shift is not read as change.

**Output:** `map_t1[6,H,W]`, `map_t2[6,H,W]`, `change_mask[H,W]`, and the derived `T[i][j] = |{p : C[p]=1, M1[p]=i, M2[p]=j}|`.

**Loss:**
```
L = L_sem_t1 + L_sem_t2 + L_change + 0.3 · L_consistency

L_sem_*      : cross-entropy on each date's semantic map
L_change     : BCE + Dice on the binary change mask
L_consistency: penalise change=0 where argmax(M1) ≠ argmax(M2), and
               change=1 where argmax(M1) = argmax(M2).
               This is the term that makes T internally coherent —
               without it the three heads disagree and the transition
               matrix is nonsense.
```

**Evaluation metrics:** SECOND's standard semantic-change metrics (mIoU, SeK, F1) on the SECOND validation split; **CDVQA accuracy on the official test splits** — this is the number that gets scored; and a **question-only blind baseline** on CDVQA, which is mandatory given the documented language bias in this benchmark.

**Training regime: TRANSFER LEARN — ImageNet-pretrained encoder, fine-tune fully.**

Note the deliberate asymmetry with M1: **M1 trains from scratch because it is data-rich (229k patches); M6 uses pretraining because it is data-poor (2,968 pairs, of which 1,600 are in the CDVQA train split).** Same team, same week, opposite decision, for a reason you can state. That asymmetry is the kind of thing a judge probes and it is satisfying to have an answer for.

**Realistic expected performance:** published SECOND semantic-change-detection numbers exist and you should look them up (Bi-SRNet / SCanNet papers); I did not verify them in this session and will not quote a figure I have not read. For CDVQA, the original paper reports baseline accuracies you can cite directly. **PRIOR: with 1,600 training pairs you will not beat the published SECOND SOTA, and you should not claim to. Aim to land within a few points of it and spend your effort on the CDVQA conversion, which is where your architecture is different.**

---

## 3.7 M7 — Vision-language model (InternVL3-1B + modality branches + LoRA)

**Task:** free-form description, change narration, answer phrasing, low-confidence fallback, and the compliance anchor for the RS-adaptation clause. **Not counting, area, adjacency, position, or boxes.**

**Model:** `OpenGVLab/InternVL3-1B` — MIT licensed, Qwen2.5-0.5B base (Apache-2.0), 1.1B total.

Architecture, following the published recipe exactly (VERIFIED from §4.2 of the paper):
```
S1 patch    → BEN-pretrained ViT (S1)  [FROZEN] → tokens → Linear proj → [T_s1]
S2 patch    → BEN-pretrained ViT (S2)  [FROZEN] → tokens → Linear proj → [T_s2]
RGB view    → InternViT-300M           [FROZEN] → tokens → native proj → [T_rgb]
instruction → tokenizer                                                → [T_txt]

LLM input = [T_s1 ; T_s2 ; T_rgb ; T_txt]
LLM = Qwen2.5-0.5B + LoRA (r=8, α=32, dropout=0.1)          [TRAINABLE]
Modality projections                                         [TRAINABLE]
→ 5.8M trainable of 1.1B
```

**Why this backbone:** the published baseline uses this exact model, so your numbers are directly comparable to a citable reference. That is worth more with a scientific judge than a marginally better number from a different backbone. License is clean. It deploys — 1B fits alongside the segmenter on one GPU. And there is PUBLISHED evidence that adaptation beats scale on this benchmark: the fine-tuned 1B model reaches 73.29 binary VQA against 60.39 for a reported-2T general model (Table 8 vs Table 2).

**Input features:** as above. Only the 10 m and 20 m S2 bands.

**Output:** text, under **constrained decoding**. Never free generation for a scored output:
- Binary: compare the logits of the yes/no tokens at the first answer position. Never generate.
- MCQ: length-normalised log-likelihood of each option, argmax. Never generate.
- Grounding: grammar-constrained decoding against the bbox format.
- Captioning / free-form: generation, since there is nothing to constrain.

**Loss:** standard next-token cross-entropy on answer tokens only; mask the instruction tokens.

**Evaluation metrics:** BLEU-4, ROUGE, METEOR, CIDEr, BERTScore, SBERT-cosine — in the paper's Table 7 layout. Plus instruction-following rate.

**Training regime: PEFT — LoRA + projection training. Do not full fine-tune.**

Curriculum (this ordering matters and skipping step 1 is a common cause of a loss plateau):
1. **Projection warm-up, LoRA frozen, ~2k steps.** Trains only the S1/S2 linear projections so the new modality tokens land somewhere sensible in the LLM's embedding space before the LLM starts adapting to them.
2. **Joint LoRA + projection training on captioning.** Densest supervision available (107 words per sample, VERIFIED) and it teaches domain vocabulary and structure.
3. Optional second adapter for change narration.
4. **Do not train VQA / MCQ / grounding adapters** unless the symbolic path fails its gate. That is the compute saving that makes this plan fit on one GPU.

**Realistic expected performance:**

> **You will probably not reproduce 34.04 BLEU-4, and you should say so up front.** The reference number came from per-task fine-tuning on train+val combined for one epoch at roughly two days on four H200s (VERIFIED). On a single 24 GB consumer GPU with a stratified subsample you are training on a fraction of that. PRIOR: expect meaningfully below the reference, and report the subsample fraction honestly in your experiment table.

The comparison that *is* fair and that you should make: **InternVL3-1B zero-shot vs your adapted version.** Published zero-shot: 0.34 BLEU-4 captioning, 54.11 binary VQA, 26.76 MCQ, 5.01 referring-LULC mIoU. Any monotone improvement over those is direct evidence against the "generic VLM without RS adaptation" disqualifier, and it is a comparison you can win with student compute.

---

## 3.8 M8 — Template→style caption rewriter (conditional)

**Task:** rewrite a factually-exact template caption into the surface style of the dataset's paraphrased captions.

**Model:** **Flan-T5-base (250M)** seq2seq fine-tune, or LoRA on Qwen2.5-0.5B-Instruct. Text-to-text only, no vision component. Trains in a few GPU-hours.

**Why:** VERIFIED that reference captions are template output paraphrased by a quantised Llama-4-Scout-17B with explicit instructions to diversify lexical and syntactic structure, followed by self-refinement, with the CLC nomenclature supplied to permit cross-level synonym substitution. Raw templates will therefore share content but not surface form with the references, and BLEU-4 is a 4-gram metric. **This is why I think the previous document's H-CAP hypothesis is over-optimistic in its raw form** (see §0.1C).

The training data is **free and exactly aligned**: you hold reBEN's reference maps and BigEarthNet.txt's released captions for the same patches. Generate your own template caption for each training patch, pair it with the released caption, and you have hundreds of thousands of (template, target-style) pairs at zero annotation cost.

**Input features:** template caption string. Optionally the attribute struct as a prefix.

**Output:** styled caption string.

**Loss:** token-level cross-entropy.

**Evaluation metrics:** BLEU-4, ROUGE, METEOR, CIDEr against released captions. **Plus a factuality check**: re-extract attributes from the rewritten caption and verify they still match the source struct. A stylizer that improves BLEU by hallucinating fluent nonsense is a regression, and you should catch it automatically.

**Training regime: FINE-TUNE.**

**The gate that decides whether to build this at all** — run it in week 2, it costs about four hours and needs no trained model:
```
1. Take ground-truth CLC maps from a validation subset.
2. Generate template captions from them.
3. Score BLEU-4 / ROUGE / METEOR / CIDEr against the released captions.
   → This is the ceiling of the symbolic captioning path with a perfect segmenter.

If ceiling ≥ ~35 BLEU-4  → raw templates are enough; skip M8 entirely.
If ~10 ≤ ceiling < ~35   → build M8. This is where I expect to land.
If ceiling < ~10         → drop the symbolic captioning path; route to M7.
```

This is still the highest expected-value experiment in the project, exactly as the previous document says. I have only changed the predicted outcome.

---

## 3.9 M9 — Confidence calibrator

**Task:** map internal signals to a calibrated P(answer is correct).

**Model:** **L2-regularised logistic regression**, followed by isotonic regression for post-hoc calibration. Five to eight features. Deliberately the simplest model that works, because you want to print its coefficients on a slide.

**Why not just use softmax:** a segmentation softmax over 44 classes tells you about pixel-level confidence, not answer-level correctness. A count can be wrong while every pixel is confidently labelled — that is precisely the failure mode where two regions get merged by a confident but wrong bridge of pixels. Answer-level confidence needs answer-level features.

**Input features:**
```
mean_class_margin       segmenter top-1 minus top-2, averaged inside components
tta_answer_stability    fraction of 8 TTA transforms giving the same answer
component_count_std     σ of the count across TTA transforms
area_interval_width     (p95 − p5) area across TTA, normalised
min_component_margin    the weakest component's margin
band_presence_fraction  how many expected bands were actually supplied
sibling_confusion_prior for the queried class, from the confusion matrix
```

**Output:** `P(correct)` ∈ [0,1], plus a three-way band (high / medium / low) at fitted thresholds.

**Loss:** log loss.

**Evaluation metrics:** **Expected Calibration Error**, Brier score, reliability diagram, **risk–coverage curve** (accuracy as a function of the fraction of questions answered). Report the coverage at which accuracy reaches a stated target — that is the number an operational judge cares about.

**Training regime: FIT** on a held-out calibration split that is used for nothing else. Not the training split (over-confident), not the benchmark split (that is cheating).

---

## 3.10 M10 — Query intent classifier (fallback path only)

**Task:** 8-way classification of a free-text query into task types, when the rule-based parser fails.

**Model:** **TF-IDF (word + char n-grams) → linear SVM**, or a fine-tuned `all-MiniLM-L6-v2` sentence classifier (~22M params). CPU only.

**Why not the 0.5B LLM the previous document proposes:** see F10. Closed 8-way classification over a vocabulary you control does not need a generative model. This trains in seconds, runs on CPU, removes a GPU dependency from the request path, and is fully auditable.

**Input features:** the query string, sanitised (control characters stripped, length capped — this is a prompt-injection defence, since metadata strings from uploaded files can reach this path).

**Output:** task label + confidence. Below threshold → ask the user to clarify rather than guess.

**Loss:** hinge (SVM) or cross-entropy (MiniLM).

**Evaluation metrics:** accuracy on a labelled set of ~300 human-paraphrased queries, plus a large auto-generated set built by permuting the benchmark's own templates. **Target ≥98%.** Report this — it is a legitimate metric and it is easy to be honest about.

**Training regime: TRAIN FROM SCRATCH** (SVM) or **FINE-TUNE** (MiniLM). Minutes either way.

---

# 4. Datasets

## 4.1 The selection principle

Before the table, the principle — because you specifically asked why each dataset is chosen rather than collected at random.

**Every dataset in this project must answer one of exactly five questions.** If a dataset does not answer one of these, it is not in the plan, however well-known it is.

| # | Question the dataset answers | Datasets |
|---|---|---|
| 1 | What does the LULC map look like? (M1's supervision) | reBEN reference maps; ESA WorldCover-India |
| 2 | What is the answer grammar? (M3/M4's supervision; the scoring target) | BigEarthNet.txt annotations |
| 3 | What does change look like? (M6's supervision + change scoring) | SECOND; CDVQA |
| 4 | What does the metadata look like? (M5's supervision) | reBEN metadata |
| 5 | **Does it work in India?** (the domain question) | Sentinel over India + WorldCover / Dynamic World / Bhuvan |

Datasets that answer none of these — SpaceNet, DOTA, xView, most of the RS zoo — are **excluded on principle**, not because they are bad, but because a different task with a different taxonomy adds training noise and reviewer confusion for no measurable gain. Say that on stage. "We deliberately did not use X" is a stronger answer than "we used everything we could find".

## 4.2 The dataset table

| Task it serves | Dataset | Source | Contents | Size / type | Target variable | Why this one specifically | Indian? | Usable for training? |
|---|---|---|---|---|---|---|---|---|
| **M1 segmentation** | **BigEarthNet v2.0 (reBEN)** — imagery + reference maps | bigearth.net; BIFOLD/TU Berlin | Co-registered Sentinel-1 GRD (VV,VH) + Sentinel-2 L2A patches, 120×120 @ 10 m, over 10 European countries, each with a **pixel-level CORINE 2018 (V2020_20u1) reference map** | 549,488 pairs total; BigEarthNet.txt uses the 464,044 that survive cloud/snow/unclassified filtering. Train 229,114 / val 118,095 / test 116,835 | **CLC Level-3 class per pixel (44 classes).** 19-class scheme is image-level only — see F1 | The **only** dataset that supplies the exact supervision the whole architecture depends on, at the exact patch geometry the benchmark uses. Non-negotiable. | No — Europe | **Yes.** Openly distributed. Confirm the exact licence text before submission. |
| **M3/M4 decision heads; the scoring target** | **BigEarthNet.txt annotations** | HuggingFace / txt.bigearth.net (parquet, ~467 MB) | 9.6M text annotations over the same 464,044 pairs: captions, binary VQA, MCQ, referring LULC + referring point detection, across 15 tasks | 4.67M train / 2.45M val / 2.42M test annotations. **Benchmark split: 1,082 pairs, 15,029 annotations** (6,927 binary, 5,550 MCQ, 970 captions, 1,582 ref-exp) | Answer strings; bounding boxes | Mandated by the problem statement, **and** it is the artefact that encodes the answer grammar we are reverse-engineering. Parsing it is a P0 task. | No | **Yes.** CDLA-Permissive-1.0 (verify). Benchmark split is **evaluation only — never train or tune on it.** |
| **M5 metadata classifier** | **reBEN metadata** (rides with the above) | Same | Country, acquisition date, geolocation, S2 tile ID per patch. Köppen zone by coordinate lookup against a public 1 km climate raster | 549,488 rows | country (10-way), season (4-way), Köppen zone | Free labels for 3 of 8 MCQ sub-categories. Costs nothing; the previous plan ignored it. | No | **Yes** |
| **M6 change model** | **SECOND** | Public subset, from the CDVQA authors' distribution | Bi-temporal aerial RGB, 0.5–3 m, over Chinese cities (Shanghai, Hangzhou, Chengdu). Two pixel-level semantic change maps per pair | 4,662 pairs total, **2,968 publicly available**, 512×512 | 6 change-relevant classes: non-vegetated ground, buildings, playgrounds, water, low vegetation, trees | It is the supervision **behind** CDVQA — verified. Training on the source of the benchmark's ground truth is the whole strategy repeated for the change path. | No — China | **Yes.** Verify licence. |
| **Change scoring** | **CDVQA** | arXiv:2112.06343 authors | Question–answer triplets auto-generated from SECOND's semantic change maps | 2,968 pairs, >122k QA pairs; train 65,967 QA / 1,600 pairs; val 16,441 QA / 400 pairs; **two official test splits** | Answers in a **closed set of 19 categories** | Mandated for the change capability. The closed answer set makes symbolic answering and a strong blind baseline both easy. | No | **Yes**, and **mandatory** to also run a question-only blind baseline on it — this benchmark has documented language bias. |
| **Grounding eval; scale robustness** | **VRSBench** | Public | Sub-metre RGB aerial with human-verified captions, referring expressions and QA | 29,614 images; 52,472 referring expressions; 123,221 QA | Captions, boxes, answers | Mandated for evaluation. Separately, it is the **only high-resolution imagery we can legally obtain**, so it is our scale-gap training signal — but for **scale-consistency objectives, not class supervision**, because its taxonomy is not CORINE. | No | Eval as mandated; train split usable for scale-consistency only |
| **VQA eval** | **RSVQA (LR + HR)** | Public | RGB aerial VQA | 77,232 LR / 1,066,316 HR triplets | Answers | Mandated for evaluation. Nothing else. | No | **Evaluation only.** Do not train on it — different taxonomy, different question distribution, adds noise. |
| **Indian geographic adaptation — imagery** | **Copernicus Sentinel-1 GRD + Sentinel-2 L2A over India** | Copernicus Data Space Ecosystem; or Google Earth Engine; or Microsoft Planetary Computer | The **identical sensors, bands, and resolution as reBEN**, over Indian territory | You choose. Recommend 20k–50k patches at 120×120 @ 10 m | None natively — pair with a label source below | **This is the answer to the Indian-data problem.** Same sensor, same GSD, same patch geometry; only the geography changes. It isolates exactly the axis of shift we can actually attack. | **Yes** | **Yes.** Free, open, unrestricted. |
| **Indian geographic adaptation — labels** | **ESA WorldCover 10 m v200** | ESA / Zenodo, CC-BY 4.0 | Global 10 m land cover, 11 classes, derived from Sentinel-1 + Sentinel-2 | Global raster; clip to your Indian patches | 11-class land cover per pixel | 10 m matches our patch resolution exactly. CC-BY is clean. Globally consistent, so European and Indian labels come from the same generator — which makes the comparison scientifically valid. | **Yes** (global, includes India) | **Yes**, as **weak labels** — stated global accuracy is well below CORINE's, so treat it as noisy supervision, not gospel. |
| **Indian labels — alternative / cross-check** | **Google Dynamic World V1** | Google Earth Engine, CC-BY 4.0 | Near-real-time 10 m land cover, 9 classes + per-class probabilities, from Sentinel-2 | Global, per-scene | 9-class land cover + probabilities | The per-pixel **probabilities** are useful: they let you weight the pseudo-label loss by label confidence, which materially reduces the harm of noisy weak supervision. | **Yes** | **Yes**, as weak labels with confidence weighting |
| **Indian labels — authoritative cross-check** | **Bhuvan LULC (NRSC/ISRO)** | bhuvan.nrsc.gov.in, Thematic Services | India-wide LULC at 1:250,000 (annual cycles from 2005–06), 1:50,000 (2005–06, 2011–12, 2015–16), and 1:10,000 under SIS-DP | Vector/raster, national coverage | ISRO's own LULC classes | **Political and scientific value out of proportion to its size.** It is ISRO's own product, in front of ISRO judges, and it lets you say "we validated against NRSC's thematic layer" rather than "we validated against a European agency's". Coarser than 10 m, so use it for **class-prior agreement and coarse validation**, not per-pixel training. | **Yes** | Validation and coarse agreement; not primary pixel training |
| **Indian sensor realism** | **Bhoonidhi open Indian EO (Resourcesat LISS-III / AWiFS, RISAT ≥5 m)** | bhoonidhi.nrsc.gov.in | Indian-sensor optical and SAR, coarser than 5 m tier | Manual download; registration required | None supplied | The only route to *Indian-sensor* imagery. Use for **unlabelled domain-shift measurement** (feature-distribution comparison, pseudo-label agreement), not supervised training. | **Yes** | Unlabelled / self-supervised only |
| **Scale robustness (optional)** | **LoveDA** | Public | 0.3 m RGB, urban and rural China, 7-class LULC | 5,987 images | 7-class LULC | Only if you have slack. Its taxonomy is not CORINE, so it serves scale-consistency, same as VRSBench. **Cut this before you cut anything else.** | No | Optional |
| **The evaluation domain** | **Cartosat-2S / RISAT pairs** | ISRO/SAC hidden set | Pre-georeferenced, co-registered optical + SAR pairs over India, undisclosed annotations | Unknown | Unknown taxonomy | **We cannot obtain it.** Cartosat-2S at 0.65–2 m sits above the open-data threshold for non-government entities. | **Yes** | **No.** Do not claim a number for it. Neither can any competing team — the gap is symmetric. |
| **Excluded on principle** | SpaceNet, DOTA, xView, iSAID | — | Building footprints, oriented objects | Large | — | Different task, different taxonomy, no measurable contribution to any of the five questions in §4.1. **Say you excluded them deliberately.** | — | **No** |

## 4.3 How the datasets combine

They do **not** get pooled into one loader. Each trains one model, on one taxonomy, with one loss. Mixing taxonomies is the single most common way student teams silently destroy a segmentation model.

```
   reBEN imagery + CLC-L3 reference maps
              │
              ├──────────────────────────────► M1 SEGMENTER (44-class, primary)
              │                                        │
   reBEN metadata (country/season/geo)                  │
              │                                        │
              └──────────────────────────────► M5 METADATA CLASSIFIER
                                                       │
                                                       ▼
                                          SYMBOLIC GEOMETRY ENGINE
                                                       │
   BigEarthNet.txt annotations                         │
   (train split, features from PREDICTED maps)         │
              │                                        │
              ├──────────────────────────────► M3 BINARY DECISION HEAD
              ├──────────────────────────────► M4 MCQ OPTION SCORER
              ├──────────────────────────────► M8 CAPTION STYLIZER (conditional)
              └──────────────────────────────► M7 VLM LoRA (captioning subset only)

   BigEarthNet.txt BENCHMARK SPLIT ─────────► EVALUATION ONLY. NEVER TOUCHED
                                               UNTIL THE FINAL RUN.

   SECOND semantic change masks
              │
              └──────────────────────────────► M6 SIAMESE CHANGE MODEL
                                                       │
                                                       ▼
                                            FROM-TO TRANSITION MATRIX
                                                       │
   CDVQA official test splits ──────────────► change answer scoring
                                               + question-only blind baseline

   Sentinel-1/2 over India + WorldCover / Dynamic World
              │
              ├── BHARAT-VAL (held out, never trained on) ──► INDIAN VALIDATION
              └── BHARAT-TRAIN ──────────────────────────────► M1 DOMAIN ADAPTATION
                                                                (§5)

   VRSBench / LoveDA (sub-metre RGB)
              └── scale-consistency objective only, NEVER class supervision
```

**Three combination rules:**

1. **One taxonomy per loss term.** CORINE-L3 for reBEN, SECOND-6 for change, WorldCover-11 for India. They meet only at the **coarse-7 aggregation level** defined in §5.3, and only for reporting.
2. **The benchmark split is quarantined.** The reference model was trained on train+val combined, so there is no clean held-out set left in the published setup. **Carve your own internal validation split out of train, by geographic block** (see F11), and do not look at the benchmark split until the final evaluation. If you tune on it you are lying to yourself, and the number you report will not survive the hidden set.
3. **Weak labels are marked as weak.** Anything derived from WorldCover or Dynamic World is tagged in the dataset index and reported separately. Never average a CORINE-supervised IoU with a WorldCover-supervised IoU into one headline number.

---

# 5. Indian-data adaptation

This is the section you said you cared most about, and it is the section where I most disagree with the previous document.

## 5.1 Decompose the gap before you try to close it

The previous plan treats "the Indian gap" as one thing and concludes it is unmeasurable. It is four things, with very different tractability:

| Axis | Training | ISRO/SAC evaluation | Can we simulate it? | Can we measure it? |
|---|---|---|---|---|
| **A. Spectral** | 10 usable S2 bands incl. red-edge + SWIR | Cartosat-2S: ~4 bands (B/G/R/NIR) | **Yes, exactly** — zero the missing bands | **Yes** — mIoU with and without |
| **B. Spatial (GSD)** | 10 m | ~0.65–2 m, a 5–15× shift | **Partly** — resample and enforce consistency | Partly — a robustness curve, not a real number |
| **C. SAR characteristics** | Sentinel-1 C-band, VV/VH, IW GRD | RISAT C-band, different modes and polarimetry | **Partly** — speckle and look-number augmentation | Partly |
| **D. Geography** | 10 European countries | **India** | **No simulation needed — get the real thing** | **YES, FULLY AND FOR FREE** |

**Axis D is the one the previous document dismisses, and it is the only one that is fully solvable.** Sentinel-1 and Sentinel-2 image India from the same sensors, at the same resolution, through the same free distribution. Indian pixel labels at 10 m are free under CC-BY. Indian LULC from ISRO's own NRSC is free.

So the correct statement is not "the Indian gap is unmeasurable". It is: **"three of the four axes are simulable and one is directly measurable, and we report all four separately."** That is a defensible, honest, scientifically valid position, and it is a much better answer to a SAC judge than "we could not get Cartosat".

## 5.2 What uses pretrained models, what gets fine-tuned, what gets built

| Component | Indian adaptation strategy | Reasoning |
|---|---|---|
| **M1 segmenter** | **Fine-tune on Indian data.** This is where the entire effort goes. | It is the only component whose errors are geography-dependent *and* for which Indian supervision exists. |
| **M2 symbolic engine** | **No adaptation needed. None. At all.** | `binary_dilation` and `scipy.ndimage.label` are geography-invariant by construction. The area of a region is pixel count × GSD² in Bengaluru exactly as in Bavaria. **This is the architecture's single greatest advantage and it should be the headline of your Indian-adaptation slide.** |
| **M3 / M4 decision heads** | **Refit only if the answer grammar changes.** | These fit the *annotation generator's* conventions, not the imagery. If the ISRO set uses the same question templates, no refit. If it uses different ones, refit on a handful of examples. Either way it is cheap. |
| **M5 metadata classifier** | **Retrain or discard.** | Country prediction over 10 European countries is meaningless in India. If the hidden set asks for Indian state or agro-climatic zone, retrain on Indian metadata. If it does not ask, discard the model at inference. |
| **M6 change model** | **Fine-tune if Indian change data is obtainable; otherwise report the gap.** | SECOND is 0.5–3 m aerial over Chinese cities. Indian bi-temporal change supervision at that resolution does not exist openly. Be honest about this. |
| **M7 VLM** | **Cannot be meaningfully adapted to India, and say so.** | **There is no Indian image–text corpus for this task.** No Indian BigEarthNet.txt exists. You cannot LoRA your way to India without Indian instruction data. This is not a failure of effort; it is the state of the field. |
| **M9 calibrator** | **Refit on Indian validation data.** | Confidence must be calibrated *in the deployment domain* or it is worse than useless. Cheap — it is a logistic regression. |

**Read the M2 and M7 rows together.** They are the argument. In a monolithic VLM design, the Indian gap lives in a component you cannot adapt. In this design, the gap lives in one dense-prediction model you *can* adapt, and the entire reasoning layer is invariant. **That is the strongest scientific case for this architecture and it is not a benchmark argument at all.**

## 5.3 Building the Indian corpus — do we need our own dataset?

**Yes, and you can build it in about a week with two people.** Here is the specification.

### BHARAT-EO: an Indian evaluation and adaptation corpus

**Construction:**

```
1. SAMPLING FRAME
   Stratify across India by:
     · agro-climatic zone (use ICAR's 15-zone or NARP's 127-zone scheme)
     · season (kharif / rabi / zaid / post-monsoon) — India's cropping
       calendar is the single biggest phenological difference from Europe
     · urban / peri-urban / rural / forest / coastal / arid
   Target: proportional-to-area with a minimum quota per stratum so that
   rare classes (mangrove, salt pan, cold desert) are represented.

2. IMAGERY
   Sentinel-2 L2A + Sentinel-1 GRD, co-registered, same processing chain
   as reBEN:
     · S2: same 10 bands, 20 m resampled to 10 m, 60 m discarded
     · S1: VV/VH, converted to dB, same normalisation
     · tile to 120×120 @ 10 m  ← MATCH reBEN's PATCH GEOMETRY EXACTLY
   Cloud-filter using the S2 SCL band, matching reBEN's filtering.
   Source: Copernicus Data Space, or Earth Engine, or Planetary Computer.

3. LABELS  (three sources, three purposes)
     · ESA WorldCover 10 m v200   → primary weak pixel labels (11 classes)
     · Dynamic World V1           → per-pixel confidence weighting
     · Bhuvan LULC 1:250k         → independent coarse cross-check, and
                                     the politically valuable one
   Agreement between WorldCover and Dynamic World is itself a useful
   signal: train on the agreeing pixels, down-weight or ignore the rest.
   This is a standard and defensible noisy-label strategy.

4. TAXONOMY BRIDGE
   Map CORINE-L3 (44) and WorldCover (11) into a COARSE-7 common set:
     built-up · cropland · tree cover · grassland-shrub · water ·
     bare-sparse · wetland
   ALL cross-domain numbers are reported at coarse-7 ONLY.
   Reporting a CORINE-L3 IoU on Indian data would be meaningless —
   CORINE classes are defined by European land-use conventions.

5. SPLITS
   BHARAT-VAL   : held out, NEVER trained on, NEVER tuned on.
                  Used once, at the end, for the headline Indian number.
   BHARAT-TRAIN : used for domain adaptation.
   Split GEOGRAPHICALLY (by state or by 1° grid cell), never randomly.
```

**How much data do you need?**

| Purpose | Patches | Reasoning |
|---|---|---|
| **BHARAT-VAL** (measurement only) | **2,000–5,000** | For a coarse-7 mIoU estimate, a few thousand stratified patches gives a 95% CI of roughly ±1–2 points — tight enough to detect the domain drop, which will be much larger than that. **You could do the measurement alone with this and it would already be more than any competing team has.** |
| **Norm-statistics re-estimation** | **500–2,000** | Re-estimating batch-norm / normalisation statistics on the target domain needs very little data and is often the single highest-return adaptation step per unit effort. Do this first. |
| **Decoder-only fine-tuning** | **10,000–20,000** | Freezing the encoder and adapting the decoder + head adapts the class prior and the decision boundaries without destroying the learned features. |
| **Full fine-tuning of M1** | **50,000–100,000+** | Only worth it if the weak-label noise is manageable and you have the GPU time. My PRIOR is that the return over decoder-only fine-tuning is modest given WorldCover's label noise. |
| **Self-supervised pretraining on Indian imagery** | 500,000+ | **Do not.** Out of scope for eight weeks and the previous document correctly ranks it P3. |

**Realistic plan: build 20,000–30,000 patches. Hold out 5,000 as BHARAT-VAL. Use the rest for norm re-estimation and decoder fine-tuning.** That is two people for a week using Earth Engine, and it is the single most differentiating thing in this project for an ISRO audience.

## 5.4 The adaptation techniques, ranked by return per hour

| Technique | Attacks axis | Effort | Compute | My assessment |
|---|---|---|---|---|
| **Band dropout** (zero red-edge + SWIR, keep B/G/R/NIR) with a learned band-presence embedding | **A (spectral)** | ~10 lines | ~0 | **P0. Highest return in the project.** This is the one axis of the shift we know exactly, and we can simulate it exactly. Train with it from step 1, not as a fine-tune. |
| **Normalisation-statistics re-estimation on Indian data** | D | Trivial | Minutes | **P0.** Forward passes only, no gradients. Often a surprisingly large chunk of the total achievable gain, for almost no cost. Do it before anything more elaborate. |
| **Configurable class-mapping layer** (taxonomy in YAML, never hard-coded) | Taxonomy | An afternoon | 0 | **P0, build it day one.** If the hidden set uses a different taxonomy, the answer becomes "give us a mapping table" instead of "we need to retrain". This is the difference between adaptable and brittle. |
| **Scale augmentation + consistency loss** (0.5×–4×, predict, resample back, penalise divergence) | **B (GSD)** | Low | Low | **P0.** Directly attacks the largest simulable axis and produces a displayable mIoU-vs-scale curve. |
| **Modality dropout** (drop S1 or S2 entirely, p≈0.15 each) | C + robustness | Trivial | ~0 | **P0.** Also makes leave-one-modality-out attribution an in-distribution operation rather than an out-of-distribution stunt, so the attribution numbers mean something. |
| **SAR speckle / look-number augmentation** | **C (SAR)** | Low | ~0 | **P0.** RISAT's speckle statistics differ from Sentinel-1 IW GRD. Multiplicative gamma with looks ∈ [2,10]. |
| **Radiometric jitter** (per-band gain/offset ±20%) | A + C | Trivial | ~0 | **P0.** Different sensors, different calibration. |
| **Decoder + last-encoder-stage fine-tune on BHARAT-TRAIN**, low LR, encoder frozen | **D (geography)** | Medium | Low | **P1. This is the Indian adaptation proper.** |
| **Confidence-weighted pseudo-label training** using Dynamic World probabilities | D | Medium | Medium | **P1.** The confidence weighting is what makes noisy weak labels safe. |
| **Test-time adaptation** (entropy minimisation on the test batch) | All | Medium | Low | **P2, implement but default OFF.** Can degrade silently and it makes results non-reproducible per-batch. A judge will ask whether your test predictions depend on what else was in the batch. |
| **Domain-adversarial training (DANN)** | D | High | Medium | **P3, do not.** Historically finicky, needs careful balancing, and you have a better option (real target labels). |
| **CORAL / MMD feature alignment** | D | Medium | Low | **P3, do not.** Designed for the case where you have no target labels. You have weak target labels, which is strictly better. |
| **Self-supervised pretraining on Indian imagery** | D | Very high | High | **P3, do not.** Right idea, wrong timescale. |

## 5.5 Which adaptation method: LoRA, PEFT, full fine-tuning, or transfer learning?

You asked this explicitly, so let me be precise, because the right answer differs per component and the standard reflex ("use LoRA") is wrong for most of them.

**M1 segmenter — NOT LoRA. Use staged fine-tuning.**

LoRA exists to make adaptation cheap when the model is enormous and full fine-tuning is infeasible. M1 is ~30–45M parameters. Full fine-tuning costs hours on a consumer GPU. There is no memory problem to solve, so LoRA's benefit is zero while its cost — constraining updates to a low-rank subspace — is real. Use instead:

```
Stage 1  Re-estimate normalisation statistics on BHARAT-TRAIN.
         Forward passes only. Minutes. Do this first and MEASURE it —
         it may get you a large fraction of the total gain alone.

Stage 2  Freeze the encoder. Fine-tune decoder + head on BHARAT-TRAIN
         at LR ≈ 1/10 of the original, for a few epochs.
         Loss: confidence-weighted CE against WorldCover/Dynamic World,
               weighted by inter-source agreement.

Stage 3  (only if Stage 2's gain is still climbing)
         Unfreeze the last encoder stage. LR ≈ 1/100. Few epochs.

Stage 4  REPLAY. Interleave European reBEN batches at ~20-30% to
         prevent catastrophic forgetting. Evaluate on BOTH domains
         after every stage.

STOP RULE: if European mIoU drops by more than ~2 points, you have
           over-adapted. Back off. You need the model to work on the
           public benchmark AND on the hidden set.
```

That replay-and-stop rule is important and the previous plan has no equivalent. Adapting hard to India while destroying your public-benchmark score is a net loss, because the public benchmark is half of what you are scored on.

**M7 VLM — LoRA, but not for India.** LoRA is already the right mechanism for adapting InternVL3-1B to remote sensing (it is the published recipe: rank 8, α 32, dropout 0.1, 5.8M trainable of 1.1B). But there is **no Indian instruction data to LoRA on**, so this adapter handles the RS domain shift, not the geographic one. State this limitation openly rather than implying the VLM is Indian-adapted.

**M6 change model — full fine-tune with an ImageNet-pretrained encoder.** Data-poor regime; pretraining helps; the model is small enough that full fine-tuning is trivial.

**M3 / M4 / M5 / M9 — refit from scratch.** They are seconds to minutes to train. "Adaptation" is just retraining them.

## 5.6 How to prevent looking good on foreign data and bad on Indian data

This is the failure mode you named, and it has a procedural answer, not a technical one. Six rules:

1. **Report both domains on every single result, always, in the same table.** European mIoU and Indian coarse-7 mIoU side by side, in every experiment row. Never report one alone. The moment you allow a European-only number into a slide, you have started deceiving yourself.

2. **BHARAT-VAL is fitted on nothing.** Not hyperparameters, not thresholds, not early stopping, not the MMU. It is looked at once, at the end. If you need a second Indian set for tuning, carve BHARAT-DEV separately — but never tune on the set you report.

3. **Split geographically, not randomly.** Adjacent Indian patches are as spatially autocorrelated as European ones. A random split will tell you the domain gap is small when it is not.

4. **Run the perturbation suite and publish the whole table**, including the rows where you lose:

| Perturbation | Simulates | Report |
|---|---|---|
| Drop SWIR + red-edge (4-band mode) | Cartosat-2S band set | mIoU delta, per class |
| Downsample 2×, 4×, then upsample | Coarser input | mIoU-vs-factor curve |
| Upsample 2×, 4× | Cartosat's finer GSD | mIoU-vs-factor curve |
| Inject speckle, looks ∈ {2,4,8} | RISAT speckle statistics | mIoU delta |
| Drop S1 entirely | Missing SAR acquisition | mIoU delta |
| Drop S2 entirely | Full cloud cover | mIoU delta |
| Radiometric gain ±20% | Calibration difference | mIoU delta |
| **Geographic shift to BHARAT-VAL** | **The real thing** | **coarse-7 mIoU, both domains** |
| All augmentations ON vs OFF | The value of the whole programme | **The headline table** |

That last row is the deliverable: two training runs, identical except for the augmentation regime, evaluated under all eight perturbations. If the augmented run degrades less under every one, **that is your evidence of transfer engineering, and it is the only honest thing anyone can say about a hidden set they have never seen.**

5. **Report the class-prior shift explicitly.** Compute the marginal class distribution of your European training data and of BHARAT-VAL, and show them side by side. Indian scenes have vastly more cropland at smaller field sizes and much less of several CORINE forest classes. A model can lose accuracy purely from prior mismatch, and that is fixable by prior correction (logit adjustment) — a cheap, principled, one-line fix that almost nobody applies.

6. **Never claim a Cartosat/RISAT number.** Report the public numbers, state the gap in the four-axis table of §5.1, present the perturbation suite as the transfer evidence, and say plainly that the sensor axis is unmeasurable without the data. **That is more persuasive than an invented figure, and a SAC judge will know the difference immediately.**

## 5.7 Regional, linguistic and cultural handling

The technical parts of this problem are geographic, not linguistic — the queries are in English and the ontology is land cover. But three things genuinely matter:

- **Taxonomy vocabulary.** Indian land-cover terminology differs from CORINE's. *Kharif fallow*, *tank*, *chena*, *scrub forest*, *salt pan*, *mangrove* are meaningful Indian categories with no clean CORINE equivalent. Put an **Indian synonym layer in the class-mapping YAML** so a query for "tank" or "water body" resolves correctly. An afternoon of work; visible payoff in a demo for an Indian audience.
- **Multilingual queries.** Not required by the problem statement. If you want it as a demo flourish, the correct implementation is a **translation front-end into the same closed intent vocabulary**, not a multilingual model. Route Hindi/Tamil/Telugu queries through IndicTrans2 (open, Indian-built, and a nice thing to cite in front of ISRO) into English, then into the existing rule-based parser. The intent space stays closed and testable. **Budget: one day. If it costs more, cut it.**
- **Phenology.** The most substantive one. India's kharif/rabi/zaid cycle means the same field is water, then dense vegetation, then bare soil within one year. Europe's calendar is different. **Stratify BHARAT-EO across seasons and report per-season Indian accuracy separately.** A model that only works in one season is not a working model, and finding that out in week 6 is much better than a judge finding it out for you.

---

# 6. Accuracy strategy

You asked me not to claim the architecture is accurate without evidence. So this section is about **how accuracy is produced and how it is proven**, not about asserting it.

## 6.1 Data cleaning

| Step | What | Why it matters here specifically |
|---|---|---|
| Patch filtering | Train M1 on the **464,044 filtered** pairs, not the full 549,488 | BigEarthNet.txt filtered out cloud, snow and unclassified-pixel patches. Training on the unfiltered set means your input distribution differs from the annotation distribution. Match them. |
| `ignore_index` | Unclassified pixels excluded from the loss | Otherwise the model learns to predict "unclassified", which is not a land-cover class and poisons the geometry engine. |
| GeoTIFF handling | **`rasterio` only. Never PIL, never OpenCV, never `imread`.** | PIL silently drops bands beyond 4, silently rescales 16-bit to 8-bit, and silently discards CRS and geotransform. Every one of those failures is invisible until your areas are wrong by a constant factor. This is the most common way a student team quietly ruins a geospatial project. |
| S1 conversion | Linear power → dB before normalisation | SAR backscatter is log-distributed. Normalising in linear space puts almost all your dynamic range in the tail. |
| Normalisation | Per-band z-score with **training-split statistics**, frozen and versioned | Per-image or per-batch normalisation leaks and breaks at single-image inference. Version the statistics file and hash it into the model card. |
| Duplicate / near-duplicate detection | Perceptual hash across the corpus | reBEN's geographic split should handle this, but verify. Near-duplicates across your internal train/val boundary inflate validation scores. |

## 6.2 Feature engineering

For dense prediction with abundant labels, most classical feature engineering is subsumed by the network. Three exceptions genuinely earn their place:

1. **Spectral indices as extra channels (NDVI, NDWI, NDBI).** Redundant given the raw bands *when all bands are present*. They matter **under band dropout**, because an index computed from surviving bands preserves a relationship the network would otherwise have to re-derive from a zeroed input. Ablate it; report the delta specifically in the 4-band condition.
2. **The band-presence embedding.** Not optional. Without it, zeroing a band teaches the model "this surface has near-zero reflectance in SWIR", which is a real physical statement about water and shadow. You need "this band was not measured", which is a different thing.
3. **Terrain, if you can get it.** Copernicus DEM 30 m is free and globally available. Slope and elevation are genuinely informative for several CORINE classes (moors, alpine pasture, bare rock) and they transfer to India without modification. Cheap. Consider it a P2 experiment.

## 6.3 Class balancing

Four mechanisms, applied together:

- **Inverse-square-root frequency weighting, capped at 5×.** Full inverse-frequency weighting at 44 classes destabilises training — a class appearing in 0.01% of pixels gets a 10,000× weight and one bad batch blows up the loss.
- **Lovász-Softmax auxiliary loss.** Directly optimises the IoU surrogate, which handles rare classes better than Dice at this class count.
- **Stratified sampling by rare-class presence.** Oversample patches containing tail classes, at a modest ratio (2–3×, not 10×). Report the ratio.
- **Report per-class IoU always.** If you report only mIoU, you cannot tell whether an improvement came from the classes the benchmark asks about or from a rare class nobody queries. The benchmark's annotations are balanced across LULC classes to the extent their natural distribution permits (VERIFIED), so tail-class performance genuinely matters here — more than it would in a typical segmentation paper.

For **M3**, the benchmark's binary annotations are balanced across answer options (VERIFIED), so balance your training set to match. Otherwise the calibration will be systematically off in the direction of the training prior.

## 6.4 Data augmentation

```
GEOMETRIC          hflip, vflip, rot90                       p=0.5 each
                   (safe: land cover has no canonical orientation)

BAND DROPOUT       keep only {B02,B03,B04,B08}               p=0.30
                   partial drop of individual non-Cartosat bands  p=0.15 each
                   + band-presence embedding                 ALWAYS

MODALITY DROPOUT   drop S1 entirely                          p=0.15
                   drop S2 entirely                          p=0.15

SCALE JITTER       resample 0.5×–4×, predict, resample back  p=0.30
                   + consistency loss against native scale

SPECKLE (S1 only)  multiplicative gamma, looks ∈ [2,10]      p=0.30

RADIOMETRIC        per-band gain/offset jitter ±20%          p=0.30

NOT USED           colour jitter in RGB space (meaningless for 12-band data)
                   mixup / cutmix (destroys the region topology the whole
                                   symbolic path depends on — do NOT use)
```

That last exclusion is worth stating explicitly on a slide. **Mixup and CutMix are standard, reflexive, and actively harmful here**, because they fabricate region boundaries and change connected-component counts. Knowing which standard technique to refuse is a stronger signal of understanding than applying all of them.

## 6.5 Pretraining and fine-tuning decisions, summarised

| Model | Decision | Why |
|---|---|---|
| M1 segmenter | **From scratch** | 229k labelled patches is data-rich; pretrained classification features cost spatial precision |
| M5 metadata | Transfer (ImageNet-init) | Scene-level classification — exactly what ImageNet features are good for |
| M6 change | Transfer (ImageNet-init) | 1,600 training pairs is data-poor |
| M7 VLM | **PEFT (LoRA r=8, α=32)** | 1.1B model, 5.8M trainable, published recipe, one GPU |
| M8 stylizer | Fine-tune | Small seq2seq, abundant free pairs |
| M3/M4/M9/M10 | From scratch | Seconds to train |
| M1 → India | **Staged fine-tune with replay** (§5.5) | Not LoRA — the model is small enough that full-parameter updates are cheap |

## 6.6 Hyperparameter tuning

**Do not run a large sweep.** With 8 weeks and one GPU, a broad hyperparameter search is a way to burn your compute budget producing noise. Instead:

- **Fix by convention** what the reference recipe fixes (LoRA rank/α/dropout, warm-up schedule) — deviating costs comparability for no gain.
- **Tune only three things for M1**, in this order of expected impact: learning rate (3 values, log-spaced), loss weights (2–3 combinations), and augmentation strength (on/off/heavy). That is ≤27 configurations if you crossed them, but you should not cross them — tune sequentially, one axis at a time, ~8 runs total.
- **Use the internal geographic-block validation split.** Never the benchmark split.
- **Budget: ~8 segmentation runs at a few hours each.** That fits.
- **The symbolic engine's parameters (connectivity, MMU, dilation radius) are fitted, not tuned** — they are recovered from ground-truth data by exhaustive small sweeps, which is a different and much cheaper operation.

## 6.7 Cross-validation

**Geographic block cross-validation, k=5, blocked by country or by 1° grid cell.**

Random k-fold is wrong here and it is worth being emphatic. Sentinel patches within a few kilometres share land-cover context, phenology, atmosphere and often the same CORINE polygon. A random split places near-identical patches in train and validation, and validation mIoU comes out several points optimistic. You then make architecture decisions with a biased instrument.

Use k=5 blocked folds for the **decision-making phase** (choosing between architectures), and a single geographic held-out split for the final model. Report the fold variance — an architecture that wins by 1 point with a 3-point fold standard deviation has not won.

## 6.8 Ensembling and stacking

**Use, in order of value per unit cost:**

1. **Test-time augmentation, 8 transforms (4 rotations × 2 flips), logits averaged.** Nearly free, reliably worth a point or two of mIoU, and it does **double duty** — the variance across transforms is the strongest input feature for M9's confidence model. Build it for confidence and get the accuracy for free.
2. **Weight averaging (SWA or last-k checkpoint averaging).** One training run, no extra inference cost, consistently small positive gain. Strictly better than nothing.
3. **2–3 model ensemble** (U-Net + SegFormer-B0), logits averaged. Real gain, but 2–3× inference cost and it complicates the "runs on one GPU" deployment story. **Only if you have slack in week 7.**

**Do not stack a meta-learner over model outputs.** With a benchmark split of 1,082 pairs you do not have the data to fit a stacker without overfitting, and it destroys the auditability that is a stated requirement.

## 6.9 Calibration

- **Temperature scaling** on M1's logits, fitted on the internal validation split. One parameter.
- **M9's logistic regression** for answer-level confidence, then **isotonic regression** on top for the final probability.
- **Refit the calibrator on BHARAT-VAL** before making any claim about Indian confidence. A calibrator fitted in Europe is not calibrated in India, and confidence that is wrong in the deployment domain is worse than no confidence at all.
- **Report ECE, Brier score, a reliability diagram, and a risk–coverage curve.** The problem statement requires confidence estimation; these are what turn that requirement into a measured quantity rather than a claim.

## 6.10 Error analysis

Four analyses, each of which should produce a figure you can put on a slide:

1. **The oracle decomposition.** Symbolic accuracy on ground-truth maps minus symbolic accuracy on predicted maps = **the exact cost of imperfect segmentation, per sub-task.** This single decomposition tells you whether to spend week 6 on segmentation or on the answer grammar. Nobody else will report it.
2. **The 44×44 confusion matrix with CLC sibling groups boxed.** The benchmark's adversarial "no" answers use semantically similar classes from the CLC hierarchy (VERIFIED), so the off-diagonal mass *inside* the sibling boxes is the mass that costs you points. Optimise against that, not against overall accuracy.
3. **Per-sub-task error attribution.** For every wrong answer, classify the cause: segmentation error / wrong connectivity convention / MMU threshold / hierarchy aggregation / decision-head boundary / parse failure. Tabulate. This tells you exactly where the next point of accuracy lives.
4. **Count-error decomposition.** For counting specifically, separate over-count (fragmentation) from under-count (merging). They have opposite fixes — opening vs closing — and averaging them together hides the signal.

## 6.11 Indian-specific validation

Covered in §5.6. The short version, restated because it is the answer to your question:

- BHARAT-VAL, geographically split, held out completely, coarse-7 taxonomy, reported alongside every European number.
- Per-season Indian accuracy reported separately.
- The eight-row perturbation table, published in full including the losses.
- Class-prior shift quantified and, if large, corrected by logit adjustment.
- No Cartosat/RISAT number, ever.

## 6.12 What a realistic target actually looks like

I am not going to give you a target accuracy, because a target set before the oracle experiment is a guess dressed as a plan. **What I will give you is the functional form the target should take**, which you fill in during weeks 2–3:

```
For each sub-task t:

   TARGET(t)  =  ORACLE(t)  ×  TRANSFER(t)

   ORACLE(t)    = symbolic accuracy on GROUND-TRUTH maps.
                  Measured in WEEK 2. Requires no trained model.
                  This is the ceiling of the entire strategy.

   TRANSFER(t)  = ratio of predicted-map accuracy to ground-truth-map
                  accuracy, measured on a first segmentation checkpoint.
                  Measured in WEEK 3.

If ORACLE(t) is low  → the answer grammar is not recovered.
                       Fix §8.4-style parquet mining. NOT a model problem.
If TRANSFER(t) is low → segmentation quality is binding.
                       Spend effort on M1.
```

This decomposition is the honest version of "our target is 85%". It has the additional virtue that when a judge asks "how do you know?", you have an answer with two measurements in it.

**What I can say with confidence about the *shape* of the results**, as a falsifiable PRIOR:

- The symbolic path will beat a fine-tuned VLM by a wide margin on **area, adjacency and relative position**.
- It will beat it on **counting**, but by less than the previous document expects, and counting will be the weakest of the computable sub-tasks. (F2)
- **Presence** will be bounded by CLC sibling confusion, not by the method — this is where the multispectral bands earn their keep and where an RGB-only competitor loses.
- **Referring expression** should be a strong result, because the 1–50% area and ≥40% bbox-fill filters remove wrong candidates for free, and **referring point detection should be near-trivial** (the box of the component containing the given point).
- **Captioning** is the highest-variance outcome. The week-2 oracle test decides it.
- **MCQ overall is capped** by the three metadata sub-tasks, which no amount of geometry will solve.

Write those down now. In week 7, check which ones were right. A team that recorded its predictions in advance and reports both the hits and the misses is doing science; a team that only reports the hits is doing marketing, and a SAC judge can tell.

## 6.13 How to prove the architecture is better than simpler alternatives

This is the part that decides whether you have a project or a submission.

**The core experiment (A1) — symbolic vs generative, matched conditions:**

| Config | Method |
|---|---|
| **Blind** | Question text only, no image. **The baseline the previous plan omits.** |
| **Majority** | Most frequent answer per sub-category |
| **VLM only** | Fine-tuned M7 answers everything |
| **Symbolic only** | Geometry engine answers everything computable |
| **Hybrid (ours)** | Router sends computable → symbolic, generative → VLM |
| **Oracle** | Geometry engine on **ground-truth** maps |

Report **per sub-category, on identical questions.** Six rows, and every one of them is informative:

- If **Blind** is close to your system, the benchmark is measuring language priors, not perception, and you need to say so.
- The **Oracle** row separates "our idea is wrong" from "our segmentation is imperfect" — the single most valuable row in the table, and one nobody else will have.
- The gap between **Symbolic only** and **Hybrid** tells you whether the router is earning its complexity.

**The statistical machinery — this is what makes it evidence rather than a table:**

1. **Bootstrap confidence intervals** on every number, resampling over the 1,082 benchmark image pairs (not over annotations — annotations within a pair are correlated, and resampling them independently will give you intervals that are too narrow).
2. **McNemar's test** for every paired comparison. Both systems answer the same items, so McNemar is the correct test and it is far more powerful than comparing two independent proportions.
3. **Report the split sizes next to the numbers**, so a reader can see the resolution of the instrument: 6,927 binary annotations (~1,700 per sub-task, 95% CI ≈ ±2.2 pts at p≈0.7); 5,550 MCQ (~700 per sub-task, 95% CI ≈ ±3.7 pts at p≈0.5); 1,582 referring-expression; 970 captions.
4. **Do not claim a difference under ~3 points on a binary sub-task or ~4 points on an MCQ sub-task.** State this rule explicitly in your report. It is the single fastest way to establish that you know what you are doing, and it protects you from a judge doing the arithmetic and finding that your headline improvement is noise.

**Matched-compute comparison.** When you compare against the VLM path, report GPU-hours for both. "We match or exceed a per-task fine-tuned VLM at roughly one-Nth of the training compute" is a much stronger claim than a raw accuracy comparison, and it is one this architecture can actually make.

**The falsification condition, stated in advance:** *a predicted LULC map plus deterministic geometry will beat a fine-tuned VLM on counting, area, adjacency, relative position and referring expressions, at a fraction of the training compute.* Run it in week 4. If it fails, you have a compliant Level-1 system already built and you fall back to the VLM path. **That is a staged bet with a real exit, not a gamble** — and stating the exit in advance is itself a credibility signal.

---

# 7. Architecture comparison

## 7.1 The three candidates

**Architecture A — the previous proposal.** Dual-path answer engine: multi-sensor segmentation + symbolic geometry + LoRA VLM + Siamese change model + cross-modal fusion attribution + symbolic caption generator + learned stylizer + confidence/abstention, behind a deterministic router, with a React/MapLibre frontend, PostGIS trace store, PDF generator and Docker deployment. Sixteen scored components.

**Architecture B — my recommendation.** Same skeleton, with: the taxonomy fixed to CLC-L3 with hierarchical aggregation; four small decision models specified explicitly (M3, M4, M5, M9); weight sharing between segmenter and VLM abandoned; six components cut; and an Indian evaluation track added as a first-class deliverable.

**Architecture C — the simple baseline.** LoRA fine-tune InternVL3-1B (or Qwen2.5-VL-3B) per task on BigEarthNet.txt, following the published recipe. One model family, no symbolic path, minimal routing, thin UI.

## 7.2 The comparison

| Criterion | **A — previous** | **B — recommended** | **C — simple baseline** |
|---|---|---|---|
| **Expected accuracy: computable sub-tasks** (count, area, adjacency, rel. pos., ref-exp) | High. Same core method as B. | **High.** Same method, plus hierarchical aggregation (which A gets wrong) and fitted decision heads (which A does not specify). | **Low.** PUBLISHED: the best evaluated frontier model reaches 55.86% on binary adjacency against a balanced set. |
| **Expected accuracy: presence** | Bounded by segmentation | **Same, slightly better** — hierarchy-aware loss targets sibling confusion, which is what the "no" answers exploit | Bounded by RGB-only pretraining; PUBLISHED best 69.34% |
| **Expected accuracy: MCQ metadata (Loc/S/Clt)** | **Weak — no model assigned** | **Better — M5 is a dedicated classifier on 229k free labels** | Moderate — general VLMs do surprisingly well here (Qwen 47.76 country, 45.93 climate) |
| **Expected accuracy: captioning** | Uncertain; A's H-CAP prediction is over-optimistic | Uncertain, but **the prediction is honest and the gate is scheduled in week 2** | Reproducible in principle (34.04 published) but **not on student compute** |
| **Data requirements** | reBEN + BEN.txt + SECOND + CDVQA + VRSBench + LoveDA + LEVIR + Bhoonidhi | **reBEN + BEN.txt + SECOND + CDVQA + BHARAT-EO.** Fewer corpora, one of them built by us. | BEN.txt only. Lowest. |
| **Training complexity** | High — 4 learned models + a stylizer + attribution machinery | **Medium** — 4 learned models, 4 fitted models, no attribution component | Low, but each per-task adapter is expensive |
| **Compute** | 1× 24 GB for 6 weeks, tight | **1× 24 GB, comfortable** — one VLM adapter, one segmenter, small heads | **Reference used 4× H200 for ~2 days.** On one consumer GPU you cannot reproduce it. |
| **Interpretability** | High — every number traceable to arithmetic | **Highest** — plus the decision heads are tabular models whose coefficients print in the trace | **Low.** A generated number has no derivation. |
| **Indian-data adaptability** | **Weak in practice.** Indian work is P2 and first on the sacrifice list; no Indian validation set exists | **Strong.** The entire gap concentrates in M1, which is adaptable with free Indian pixel labels. BHARAT-VAL gives a measured Indian number. | **Very weak.** The gap lives in a VLM that cannot be adapted without Indian image–text data, which does not exist. |
| **Research novelty** | High | **High, and better evidenced** — the oracle decomposition, the blind baselines and the measured Indian track are what make it publishable rather than merely clever | **None.** It reimplements a recipe linked from the problem statement. |
| **Overfitting risk** | Medium — many components, small benchmark split, temptation to tune on it | **Lower** — fewer fitted components, geographic blocking, quarantined benchmark split, explicit significance rules | Low on the benchmark; **high risk of overfitting to Europe**, which is invisible until the hidden set |
| **Delivery risk (8 weeks, 6 students)** | **High.** Sixteen components, ~48 person-weeks budgeted, several members learning RS from scratch | **Medium.** Six components cut. Still ambitious. | **Low**, but the ceiling is low too |
| **Compliance with the five mandatory clauses** | Full | **Full** | Partial — a single VLM with thin routing sits close to the explicit disqualifier |

## 7.3 The recommendation

**Build Architecture B.**

The reasoning, in the order that matters:

1. **The core bet is verified, not assumed.** I read the annotation-generation pipeline and confirmed that presence, counts, sizes and adjacency are extracted directly from the pixel-level reference maps and composed into templates. The answers are measurements. Treating them as measurements is correct.

2. **B fixes an error in A that would have cost real points.** The 19-class-vs-L3 taxonomy mismatch is not a detail; it invalidates A's segmentation head and every accuracy estimate downstream of it. Hierarchical aggregation at query time is a genuine architectural addition, not a refinement.

3. **B specifies the models A left as gaps.** The binary tolerance decision, the MCQ option scorer, the metadata classifier and the confidence combiner all exist implicitly in A and are named, specified and given losses and metrics in B. You asked for "a specialized model for each individual task"; this is what that actually looks like.

4. **B is the only one of the three that answers your Indian question.** A defers it; C cannot address it in principle. B concentrates the entire domain gap into one adaptable model and adds a measured Indian validation track built from free data.

5. **B is smaller than A**, and the largest risk in this project is not a wrong architecture — it is running out of weeks.

**Choose C instead if, and only if:** you cannot secure a GPU by end of week 1, or fewer than four of six team members can commit substantial time. In that case build C properly, measure it honestly, and you will have a competent submission. **Do not build a half-finished B.** A complete simple system beats an incomplete sophisticated one, every time, in front of judges who can only evaluate what runs.

## 7.4 What to cut from Architecture A, explicitly

| Cut | Reason |
|---|---|
| **Cross-modal fusion attribution as a separate component** | Keep it as an **experiment** (leave-one-modality-out inference, reported in the ablation table). It does not need to be a runtime service with its own code path. The gated-fusion SE weights already give you a readable per-channel attribution for free. |
| **The learned caption stylizer, unless the week-2 gate passes** | Conditional by construction. Do not build it speculatively. |
| **LEVIR-CD / LEVIR-CC** | Adds a third change taxonomy for no scored gain. |
| **LoveDA** | Cut before anything else. VRSBench already provides the sub-metre scale signal. |
| **NISAR** | Speculative, unavailable, and speckle augmentation already covers the polarisation-robustness argument. |
| **The 0.5B LLM query-classification fallback** | Replaced by M10 (TF-IDF + SVM). Removes a GPU dependency from the request path. (F10) |
| **Test-time adaptation** | Implement if you like, default OFF, and say why. |
| **Multi-scale training** | Keep single-scale training plus scale-consistency augmentation. The consistency loss gives you most of the benefit at a fraction of the cost. |
| **Frontend polish beyond the fixed budget** | The score does not move when the UI improves. The map, the overlay, the trace panel and the evidence panel. Nothing else. |

**What you must never cut:** the symbolic path, the evaluation harness, the execution trace, input validation, the oracle experiment, BHARAT-VAL, or any of the five mandatory capabilities.

---

# 8. Final implementation blueprint

One definitive path. Everything above collapses into this.

## 8.1 The blueprint

```
╔════════════════════════════════════════════════════════════════════════════╗
║  STEP 0 — DATASETS                                                          ║
╠════════════════════════════════════════════════════════════════════════════╣
║  reBEN imagery + CLC-L3 pixel reference maps    → M1 supervision            ║
║  reBEN metadata (country/season/geo)            → M5 supervision            ║
║  BigEarthNet.txt annotations (train split)      → M3/M4/M7/M8 supervision   ║
║  BigEarthNet.txt BENCHMARK split                → EVALUATION ONLY, QUARANTINED║
║  SECOND semantic change masks                   → M6 supervision            ║
║  CDVQA official test splits                     → change evaluation         ║
║  BHARAT-EO (built by us: S1+S2 India + WorldCover) → Indian adaptation + val║
║  VRSBench / RSVQA                               → mandated evaluation       ║
╚════════════════════════════════════════════════════════════════════════════╝
                                     ↓
╔════════════════════════════════════════════════════════════════════════════╗
║  STEP 1 — PREPROCESSING                                                     ║
╠════════════════════════════════════════════════════════════════════════════╣
║  rasterio ONLY (never PIL/OpenCV)                                           ║
║  S1: linear → dB → z-score (frozen train statistics, versioned + hashed)    ║
║  S2: 20 m → 10 m bilinear; 60 m discarded; z-score (same statistics file)   ║
║  optional index channels: NDVI, NDWI, NDBI                                  ║
║  band-presence mask [10] → learned embedding                                ║
║  reBEN GeoTIFF → rico-hdl → LMDB / safetensors  (random access at scale)    ║
║  augmentation: geometric · band dropout · modality dropout · scale jitter · ║
║                speckle · radiometric.   NO mixup, NO cutmix.                ║
║  splits: reBEN geographic split; internal val carved by GEOGRAPHIC BLOCK    ║
╚════════════════════════════════════════════════════════════════════════════╝
                                     ↓
╔════════════════════════════════════════════════════════════════════════════╗
║  MODEL 1 — MULTI-SENSOR LULC SEGMENTER            [THE ENGINE]              ║
╠════════════════════════════════════════════════════════════════════════════╣
║  Architecture : Dual-encoder U-Net, ConvNeXt-V2-Tiny encoders,              ║
║                 gated (SE) fusion at every skip, full-res decoder           ║
║                 head → 44 classes (CLC L3) + aux 19-class + aux coarse-7    ║
║  Baseline to beat : single-encoder early fusion, smp.Unet(in_channels=12)   ║
║  Candidate two    : SegFormer-B0, 12-channel stem                           ║
║  Dataset      : reBEN, 229,114 train patches (geographic split)             ║
║  Training     : FROM SCRATCH. AdamW lr 3e-4, wd 1e-4, cosine + 5% warm-up,  ║
║                 bf16, batch 128 @ 120×120, 30–50 epochs                     ║
║  Loss         : CE(ignore=unclassified, inv-sqrt weights capped 5×)         ║
║                 + 0.5·Lovász + 0.3·hierarchy-weighted + 0.2·scale-consistency║
║  Inference    : 8× TTA (4 rot × 2 flip), logits averaged                    ║
║  Metrics      : DOWNSTREAM SYMBOLIC ACCURACY (primary decision metric)      ║
║                 mIoU @ L3-44 / @19 / @coarse-7, per-class IoU, sibling      ║
║                 confusion matrix, 8-row perturbation table                  ║
║  Purpose      : produce the map every symbolic answer is computed from.     ║
║                 THE ONLY COMPONENT CARRYING THE INDIAN DOMAIN GAP.          ║
╚════════════════════════════════════════════════════════════════════════════╝
                                     ↓
╔════════════════════════════════════════════════════════════════════════════╗
║  MODEL 2 — HIERARCHY-AWARE SYMBOLIC GEOMETRY ENGINE   [DETERMINISTIC]       ║
╠════════════════════════════════════════════════════════════════════════════╣
║  Implementation : scipy.ndimage + skimage.measure                           ║
║  FITTED params  : connectivity (4 vs 8) · MMU · opening kernel ·            ║
║                   adjacency dilation radius                                 ║
║                   → fitted against GROUND-TRUTH maps in week 2              ║
║                   → RE-FITTED against PREDICTED maps in week 5              ║
║  Step 0 (NEW)   : aggregate L3(44) → the CLC level the question asks about, ║
║                   via configs/taxonomy/*.yaml. Connected components run on  ║
║                   the AGGREGATED mask, never on L3.                         ║
║  Operations     : presence · count · area(×GSD², round 1000 m²) ·           ║
║                   adjacency(dilate ∩) · relative position(centroid delta) · ║
║                   referring box(filter 1–50% area AND ≥40% bbox fill) ·     ║
║                   referring point(bbox of component containing the point) · ║
║                   caption attributes(tiers: >25% / 5–25% / <5%)             ║
║  Metric         : ORACLE exact-match vs released annotations. Target ≥99%.  ║
║  Purpose        : compute what can be computed. Geography-invariant.        ║
╚════════════════════════════════════════════════════════════════════════════╝
                                     ↓
╔════════════════════════════════════════════════════════════════════════════╗
║  MODEL 3 — BINARY DECISION HEAD          MODEL 4 — MCQ OPTION SCORER        ║
╠════════════════════════════════════════════════════════════════════════════╣
║  M3  LightGBM (~200 trees, d=4)          M4  fitted-metric distance         ║
║      or L2 logistic regression               (log scale for areas,          ║
║      features: computed · stated ·            rank scale for counts)        ║
║        log-ratio · margin · TTA σ ·          + M5 posteriors for Loc/S/Clt  ║
║        subtype · class · sibling prior       → 4-way softmax over options   ║
║      → P(yes)                                                               ║
║  Dataset : BEN.txt train annotations, features from PREDICTED maps          ║
║            (so the head learns to correct M1's systematic biases)           ║
║  Training: from scratch. Loss: BCE (M3) / 4-way CE (M4)                     ║
║  Metrics : per-subtype accuracy (Table 3 / Table 4 layout), AUC, ECE        ║
║  Purpose : convert computed quantities into the benchmark's answer formats  ║
╚════════════════════════════════════════════════════════════════════════════╝
                                     ↓
╔════════════════════════════════════════════════════════════════════════════╗
║  MODEL 5 — SCENE METADATA CLASSIFIER                                        ║
╠════════════════════════════════════════════════════════════════════════════╣
║  Architecture : ConvNeXt-Tiny, 12-channel stem, 3 linear heads              ║
║  Dataset      : reBEN metadata — country (10), season (4), Köppen zone      ║
║  Training     : TRANSFER (ImageNet-init, full fine-tune). A few GPU-hours.  ║
║  Loss         : sum of 3 class-balanced cross-entropies                     ║
║  Metrics      : top-1 per attribute; derived 4-option MCQ accuracy          ║
║  Purpose      : solve the 3 of 8 MCQ sub-categories geometry cannot touch   ║
║  GATE         : if the harness supplies metadata, these become lookups →    ║
║                 DISCARD THIS MODEL. Check the parquet in week 1.            ║
╚════════════════════════════════════════════════════════════════════════════╝
                                     ↓
╔════════════════════════════════════════════════════════════════════════════╗
║  MODEL 6 — SIAMESE SEMANTIC CHANGE MODEL              [THE CHANGE PATH]     ║
╠════════════════════════════════════════════════════════════════════════════╣
║  Architecture : Siamese U-Net, SHARED ImageNet-pretrained encoder,          ║
║                 heads: semantic_t1, semantic_t2 (shared weights, 6-class),  ║
║                 change (binary, from concat[f1, f2, |f1−f2|])               ║
║                 Reference implementations: Bi-SRNet, SCanNet                ║
║  Dataset      : SECOND (2,968 public pairs) → CDVQA official test splits    ║
║  Training     : TRANSFER (ImageNet-init, full fine-tune) — data-poor regime,║
║                 the DELIBERATE OPPOSITE of M1's from-scratch decision       ║
║  Loss         : CE(t1) + CE(t2) + [BCE+Dice](change) + 0.3·consistency      ║
║  Augment      : SAME geometry both dates · INDEPENDENT photometric jitter · ║
║                 0–2 px random shift of T2                                   ║
║  Output       : from-to transition matrix T[i][j] under the change mask     ║
║  Metrics      : SECOND mIoU/SeK/F1 · CDVQA official test accuracy ·         ║
║                 **QUESTION-ONLY BLIND BASELINE (mandatory)**                ║
║  Purpose      : make change VQA arithmetic over T, same as the main path    ║
╚════════════════════════════════════════════════════════════════════════════╝
                                     ↓
╔════════════════════════════════════════════════════════════════════════════╗
║  MODEL 7 — VLM (compliance, language, fallback)                             ║
╠════════════════════════════════════════════════════════════════════════════╣
║  Base         : OpenGVLab/InternVL3-1B (MIT; Qwen2.5-0.5B base, Apache-2.0) ║
║  Adaptation   : + frozen BEN-pretrained S1/S2 ViT branches                  ║
║                 + trainable linear projections                              ║
║                 + LoRA r=8, α=32, dropout=0.1 on the LLM  → 5.8M trainable  ║
║  Dataset      : BEN.txt captioning subset (stratified subsample — REPORT    ║
║                 THE FRACTION)                                               ║
║  Training     : PEFT. Warm-up 1e-6→1e-4 over first 1% of steps, then cosine.║
║                 Curriculum: (1) projections only ~2k steps                  ║
║                             (2) joint LoRA + projections on captioning      ║
║                 DO NOT train VQA/MCQ/grounding adapters unless the symbolic ║
║                 path fails its week-4 gate.                                 ║
║  Decoding     : binary → yes/no logit comparison, never generate            ║
║                 MCQ    → length-normalised log-likelihood, never generate   ║
║                 boxes  → grammar-constrained decoding                       ║
║  Metrics      : BLEU-4/ROUGE/METEOR/CIDEr/BERTScore (Table 7 layout) + IF   ║
║  Purpose      : free-form language, captioning fallback, RS-adaptation      ║
║                 compliance, low-confidence fallback in benchmark mode       ║
║  HONEST NOTE  : reproducing 34.04 BLEU-4 requires ~4×H200×2 days. You are   ║
║                 not going to. Report the subsample fraction and compare     ║
║                 against InternVL3-1B ZERO-SHOT, which you can beat.         ║
╚════════════════════════════════════════════════════════════════════════════╝
                                     ↓
╔════════════════════════════════════════════════════════════════════════════╗
║  MODEL 8 — TEMPLATE→STYLE REWRITER            [CONDITIONAL]                 ║
╠════════════════════════════════════════════════════════════════════════════╣
║  Architecture : Flan-T5-base (250M) seq2seq, or LoRA on Qwen2.5-0.5B        ║
║  Dataset      : (our template caption, released caption) pairs — FREE and   ║
║                 exactly aligned, generated from reBEN maps                  ║
║  Training     : FINE-TUNE. Text-to-text only. A few GPU-hours.              ║
║  Metrics      : BLEU-4/ROUGE/METEOR/CIDEr + AUTOMATED FACTUALITY CHECK      ║
║                 (re-extract attributes from the rewrite; they must match)   ║
║  GATE (week 2): score template captions from GROUND-TRUTH maps.             ║
║                 ≥35 BLEU-4 → skip M8, templates suffice                     ║
║                 10–35     → build M8   ← where I expect to land             ║
║                 <10       → drop symbolic captioning, route to M7           ║
╚════════════════════════════════════════════════════════════════════════════╝
                                     ↓
╔════════════════════════════════════════════════════════════════════════════╗
║  FUSION / DECISION LAYER                                                    ║
╠════════════════════════════════════════════════════════════════════════════╣
║  M9  CALIBRATOR — logistic regression + isotonic → P(answer correct)        ║
║      features: class margin · TTA answer stability · component-count σ ·    ║
║                area interval width · min component margin ·                 ║
║                band-presence fraction · sibling-confusion prior             ║
║      fitted on a HELD-OUT CALIBRATION SPLIT (not train, not benchmark)      ║
║      REFITTED on BHARAT-VAL before any Indian confidence claim              ║
║      reports: ECE · Brier · reliability diagram · risk–coverage curve       ║
║                                                                             ║
║  This is a CASCADE, not a vote. No ensembling across the specialist models. ║
║  Each answer has ONE producer; M9 decides whether to trust it.              ║
║                                                                             ║
║  operational mode : P<τ → abstain, naming the class and the reason          ║
║  benchmark mode   : NEVER abstain →                                         ║
║                     symbolic → M7 VLM → class prior → majority answer       ║
║  Report how often each rung fires.                                          ║
╚════════════════════════════════════════════════════════════════════════════╝
                                     ↓
╔════════════════════════════════════════════════════════════════════════════╗
║  FINAL OUTPUT                                                               ║
╠════════════════════════════════════════════════════════════════════════════╣
║  ANSWER ASSEMBLER                                                           ║
║    HARD RULE: the number comes from the geometry engine.                    ║
║               A language model may PHRASE an answer; it may never           ║
║               PRODUCE the number in it. Numbers are substituted into        ║
║               templates. This single rule is what makes the trace mean      ║
║               anything.                                                     ║
║                                                                             ║
║  → structured JSON : value · unit · confidence · evidence references        ║
║  → evidence        : mask overlay · numbered component contours · boxes ·   ║
║                      per-component area table · margin heatmap ·            ║
║                      GeoJSON + GeoTIFF export                               ║
║  → execution trace : task · tools · bound parameters · per-stage timings ·  ║
║                      model name + weights hash. Append-only.                ║
║  → PDF report      : query · inputs · map · arithmetic · confidence ·       ║
║                      trace · model hash · dataset attributions              ║
╚════════════════════════════════════════════════════════════════════════════╝
```

## 8.2 Build order

Dependency-aware, and deliberately front-loading the experiments that can invalidate the plan.

| Week | Build | Gate — the number that must exist by Friday |
|---|---|---|
| **1** | Data pipeline (reBEN → LMDB). **Parse the parquet: answer grammar, taxonomy level, distractor spacing, metadata fields.** Taxonomy YAML + class-mapping layer. Evaluation harness skeleton. Licence audit. | `docs/ANSWER_GRAMMAR.md` exists and answers: which CLC level do questions use; what metadata rides along; how are distractors spaced |
| **2** | **Symbolic geometry engine against ground-truth maps.** Fit connectivity / MMU / dilation. **Run the captioning oracle.** Run the blind + majority baselines. Start BHARAT-EO collection. | **ORACLE symbolic accuracy per sub-task** (the ceiling of the whole strategy) and **oracle caption BLEU-4** (the M8 decision) |
| **3** | Train M1 (three candidates, one harness). Measure downstream symbolic accuracy on predicted maps. Router + stubbed backend. | **mIoU @ L3/19/coarse-7** and **TRANSFER factor per sub-task** |
| **4** | **A1 ablation: symbolic vs VLM vs blind vs oracle.** M3/M4 decision heads. M5 metadata classifier. Emergency RGB-only VLM adapter. | **The falsification test.** If symbolic loses on the computable sub-tasks, fall back to the VLM path now, with four weeks left. |
| **5** | M6 change model + CDVQA conversion. **Re-fit symbolic parameters on predicted maps.** M9 calibrator. Frontend against real endpoints. | CDVQA accuracy + the blind baseline; ECE and risk–coverage curve |
| **6** | M7 VLM adapter. M8 stylizer if gated in. **BHARAT-VAL evaluation — the Indian number.** Indian domain adaptation stages 1–2. | **European and Indian numbers, side by side, in one table** |
| **7** | Full ablation suite. Perturbation table. Bootstrap CIs and McNemar tests. Error analysis. PDF report. | The complete results tables, in the paper's layout |
| **8** | Freeze. Rehearse. Write the honest-limitations slide. | Nothing new is built in week 8 |

## 8.3 The three numbers that decide everything, and when you get them

1. **End of week 2 — oracle symbolic accuracy on ground-truth maps.** This is the ceiling of the entire strategy and it costs no GPU time at all. If it is high, the architecture is validated before you have trained anything. If it is low, you have not recovered the answer grammar and you fix that, not the model.
2. **End of week 3 — downstream symbolic accuracy on predicted maps.** Divided by the oracle, this is your transfer factor and it tells you whether to spend the rest of the project on segmentation or on the answer grammar.
3. **End of week 6 — coarse-7 mIoU on BHARAT-VAL, next to the European number.** This is the number no competing team will have, and it is the one an ISRO judge will remember.

## 8.4 The one-sentence version

**Learn what must be learned, compute what can be computed, concentrate the domain gap into the one model you can actually adapt, and measure everything — including the things that did not work.**

---

## Appendix A — Published reference numbers

All transcribed from arXiv:2603.29630, Tables 2–8, which I read directly during this review. Percentages.

| Model | Captioning (BLEU-4) | Binary VQA | MCQ | Ref. Exp. Detection |
|---|---|---|---|---|
| Best evaluated RS-specific model | 1.66 | 58.38 | 35.26 | 16.18 |
| Best evaluated general CV model | 0.96 | 61.96 | 37.55 | 31.73 |
| InternVL3-1B, zero-shot | 0.45 | 54.11 | 26.76 | 5.76 |
| **RS-InternVL (fine-tuned reference)** | **34.04** | **73.29** | **51.49** | **65.84** |

Selected binary VQA sub-task results, which are the ones the symbolic path targets:

| Model | Presence | Area | Count | Adjacency |
|---|---|---|---|---|
| Best evaluated RS model (EarthMind, RGB) | 69.34 | 56.20 | 51.07 | 55.97 |
| Frontier general model (reported ~2T params) | 61.59 | 67.38 | 61.94 | **55.86** |
| Qwen3-VL-8B | 64.33 | 66.62 | 62.33 | 58.45 |

**Read the adjacency column.** A frontier model with a reported two trillion parameters reaches 55.86% on a balanced yes/no question about whether two land-cover regions touch. `scipy.ndimage.binary_dilation` computes that exactly, in microseconds, given a correct map. That single number is the entire thesis of this project, and it is published, citable, and in a table the judges can look up.

**Important caveats to state alongside these numbers:**
- The RS-InternVL row is **not one model.** It is four-plus separately fine-tuned per-task adapters, trained on train+val combined for one epoch, at approximately two days on four H200 GPUs. Anyone claiming to beat it with a single unified model is comparing unlike things. Saying so reads as rigour.
- Because they trained on train+val, **there is no clean held-out validation set left** in the published setup. Carve your own out of train, by geographic block.
- Answers were extracted even when models did not adhere to the specified output format, so the published numbers are already generous to the weaker models.

## Appendix B — Open questions requiring an owner and a deadline

| # | Question | Why it is decision-critical | Resolve by |
|---|---|---|---|
| 1 | At which CLC level do the benchmark's questions name classes — L1, L2, L3, or mixed? | Determines the segmentation target and the aggregation table. **The single highest-impact unknown.** | Week 1, from the parquet |
| 2 | What metadata rides along with each annotation (season, country, climate zone, geolocation)? | Decides whether M5 is a model or a lookup — or a discard | Week 1, from the parquet |
| 3 | Connectivity convention: 4 or 8? | Swings every counting answer | Week 2, by fitting against released counts |
| 4 | Distractor spacing for MCQ area and count | Tells you precisely how accurate M1 must be. A design input. | Week 1, from the parquet |
| 5 | Tolerance band for binary area/count "yes" | Determines M3's feature design | Week 2 |
| 6 | Does "or the any open source training data" in the problem statement permit corpora beyond BigEarthNet.txt? | If denied, the change path is impossible — BigEarthNet.txt is single-timestamp — so some external corpus must be permitted. Ask in writing. | Idea round |
| 7 | Does the ISRO/SAC hidden set exercise all five capabilities, or focus on the cross-modal pair? | The wording suggests cross-modal is central. If so it deserves more investment than its benchmark weight implies. | Idea round |
| 8 | Licence status of SECOND, CDVQA, VRSBench, and the reBEN pretrained checkpoints | "Are your training data legally usable?" should get a table, not a hesitation | Week 1 |
| 9 | Were the reBEN pretrained checkpoints trained on train only, or train+val+test? | If the latter, using them leaks into your evaluation | Week 1, from the model cards |
| 10 | Is Bhoonidhi data at ≥5 m genuinely open for a non-government entity under current policy? | A policy claim made on stage in front of SAC judges must be right | Week 1 — verify directly, do not repeat a second-hand claim |

---

*Prepared as a critical review of `SatQuery_AI_Architecture.pdf`. Primary sources for all VERIFIED claims: arXiv:2603.29630 (BigEarthNet.txt), arXiv:2605.03189 (Sentinel2Cap, for reBEN label structure), arXiv:2112.06343 (CDVQA), and NRSC/Bhuvan thematic services documentation. Every number is labelled PUBLISHED, PRIOR, or explicitly unavailable. Replace the PRIORs with measurements as they arrive.*
