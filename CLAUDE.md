# CLAUDE.md — SatQuery Standing Project Rules

This file is read automatically by Claude Code at the start of every session.
Everything here applies to **every stage**, whether or not the stage prompt repeats it.

---

## 0. PROJECT IDENTITY

**Project:** SatQuery — Satellite Image Question Answering
**Target:** Smart India Hackathon final prototype, demonstrated to judges
**Source of truth:** `docs/architecture/SatQuery_Architecture.pdf` (Architecture B)
**Core philosophy:** *Predict what needs perception; calculate what can be calculated.*

This is not a demo, not a notebook collection, not a proof of concept.
It is the final prototype that must survive technical scrutiny.

---

## 1. FROZEN ARCHITECTURE FACTS — NEVER DRIFT FROM THESE

If any generated code, comment, doc, or answer contradicts this table, it is a bug.

| Fact | Locked value |
|---|---|
| Segmentation taxonomy | **CORINE Level-3, 44 classes** |
| 19-class vocabulary | Image-level multi-label only. **NOT** the segmentation target. Auxiliary head only. |
| M1 input | Sentinel-1 (2 ch: VV, VH) + Sentinel-2 (10 ch: B02,B03,B04,B05,B06,B07,B08,B8A,B11,B12) = **12 channels** |
| M1 output | 44 × 120 × 120 logits → argmax → 120 × 120 class map |
| M1 model | Dual-encoder U-Net, ConvNeXt-V2-Tiny encoders, 1×1 conv fusion + SE gate, ~30–45M params |
| M1 training | **From scratch.** ImageNet init is an ablation, not the default. |
| M1 loss | `L_CE + 0.5·L_Lovasz + 0.3·L_hier + 0.2·L_scale` |
| M2 | Deterministic. `scipy.ndimage` + `skimage.measure`. **No neural network.** |
| M3 | Binary YES/NO head. LightGBM (~200 trees, depth 4) or L2 logistic regression. |
| M4 | MCQ option scorer. Fitted distance (log for area, rank for count) + softmax. |
| M5 | ConvNeXt-Tiny, 12-ch input, 3 heads (country / season / Köppen climate). |
| M6 | Siamese U-Net, shared weights, SECOND taxonomy (6 classes), ImageNet-pretrained. |
| M6 loss | `semantic_T1 + semantic_T2 + change + 0.3·consistency` |
| M7 | `OpenGVLab/InternVL3-1B` + LoRA (r=8, alpha=32, dropout=0.1), ~5.8M trainable of ~1.1B |
| M8 | Flan-T5-base (250M) or Qwen2.5-0.5B-Instruct LoRA. **Conditional — build only if gate says so.** |
| M9 | L2 logistic regression + isotonic regression → P(answer correct) |
| M10 | TF-IDF → Linear SVM → 8-way intent classification |
| Image loading | **`rasterio` only.** Never PIL, OpenCV, or generic `imread` for GeoTIFFs. |
| Routing | **Deterministic.** No LLM chooses tools. No `eval()`. No dynamic plugin loading. Pydantic-validated tool plans. |
| Validation split | **Geographic block CV, k=5** (country blocks or 1° grid cells). Never random split. |
| Augmentation | Flips, rotations, band dropout, modality dropout, scale jitter 0.5×–4×, SAR speckle, radiometric jitter. **NEVER Mixup or CutMix** (they corrupt connected-component logic). |

---

## 2. THE NUMBER-FLOW RULE (highest-priority architectural rule)

```
Image -> M1 -> M2 -> NUMBER -> assembler
```

A language model **may phrase** an answer. A language model **may never produce the numerical
value**. Never parse a number out of a VLM sentence and use it as the answer.

Components communicate with **typed structures** (tensors, maps, probability vectors, dataclasses/
Pydantic models) — **never with natural language**. `M1 -> sentence -> M7 -> sentence -> M3` is
explicitly forbidden.

---

## 3. HALT-AND-ASK PROTOCOL

You do **not** have authority to fix a bad number by changing the architecture.

When any of these happen, **stop work immediately** and emit a Gate Report:

- A measured metric falls below the stage's stated threshold
- A metric drops relative to the previous recorded result
- The architecture is ambiguous about what to do
- A dataset, model weight, or dependency is unavailable
- Something can only be resolved by a design decision

**Gate Report format (mandatory):**

```
=== GATE REPORT — DECISION REQUIRED ===
Stage:
Metric / observation:
Measured value:
Expected / threshold:
Delta vs previous:

Diagnosis performed (tick what was actually checked, not what was assumed):
  [ ] dataset integrity   [ ] labels        [ ] preprocessing
  [ ] leakage             [ ] split         [ ] feature quality
  [ ] class imbalance     [ ] model assumptions
  [ ] hyperparameters     [ ] pipeline bug  [ ] evaluation bug

Root-cause hypothesis:
Evidence supporting it:
Evidence against it:

Options:
  A) <action> — cost: <time/compute> — risk: <...> — expected effect: <...>
  B) ...
  C) ...

Recommendation:
STATUS: HALTED — WAITING FOR YOUR DECISION
```

Then **stop and wait.** Do not proceed to the next stage. Do not "try option A while waiting."

---

## 4. TRAINING RUNBOOK PROTOCOL

You cannot run multi-hour GPU training inside a session. When a stage requires training:

1. Write the training code, config, dataloader, and a **smoke test** (overfit 10 batches).
2. Run the smoke test yourself and report its result.
3. Emit a **Training Runbook** for the human to execute:

```
=== TRAINING RUNBOOK ===
What this trains:
Exact command(s):
Config file used:
Hardware required (GPU/VRAM/RAM/disk):
Estimated wall-clock:
Checkpoint output path:
Logs / metrics output path:
How to tell it is going wrong early:
What to paste back to me when done:
  - final metrics block
  - per-class IoU table
  - training curve (loss + val metric)
  - any crash traceback
```

4. **Stop.** Wait for the human to return with real numbers.
5. Never simulate, estimate, or invent what training "would have" produced.

---

## 5. NO FAKE RESULTS — ABSOLUTE

Never fabricate accuracy, metrics, dataset statistics, test results, or API behaviour.
Never hardcode impressive-looking outputs. Never claim a test passed that was not executed.

If something was not run, write exactly: `NOT YET VERIFIED`
If something failed, report the failure and the traceback.
If an assumption is unvalidated, mark it: `ASSUMPTION — REQUIRES VALIDATION`
If the architecture is ambiguous, say so instead of inventing a resolution.

---

## 6. CHANGE CONTROL

The architecture is fixed by default. Never silently substitute a model, dataset, loss, or
pipeline because it is easier. To propose a change, emit:

```
=== PROPOSED ARCHITECTURE CHANGE ===
Original (with architecture doc section reference):
Problem observed:
Evidence (measured, not assumed):
Proposed replacement:
Expected benefit:
Risk:
Testing required to validate:
DECISION: WAITING FOR APPROVAL
```

Minor implementation improvements that do not alter intended behaviour may be made, but must be
logged in `reports/experiments/EXPERIMENT_LOG.md`.

---

## 7. DATA DISCIPLINE

- **Quarantine:** the benchmark evaluation split (1,082 image pairs / 15,029 annotations) is
  sealed. It may be touched **once**, at final evaluation. Enforce this in code — a loader guard
  that raises unless `ALLOW_BENCHMARK_EVAL=1` is set.

- **FORBIDDEN INPUT FEATURES — `country`, `season`, `climate_zone`.** These three BigEarthNet.txt
  columns are **answer labels, never model inputs, anywhere in the pipeline.** Measured at S3:
  they are **100.00% identical** to the correct MCQ answer for their own task
  (country 35,561/35,561; season 35,561/35,561; climate zone 35,562/35,562). Feeding any of them
  to any model — as a feature, an auxiliary target used at inference, a routing signal, or a
  prompt field — is target leakage, not inference, and it silently invalidates the M5 gate and
  every metadata-MCQ number downstream. This holds regardless of what S15 decides about M5's
  existence. `latitude`/`longitude` are the same hazard by proxy, since country and climate zone
  are lookups from them. Enforce at the dataloader boundary, not by convention.
- Any preprocessing that **learns parameters** (normalization statistics, class weights, TF-IDF
  vocabulary, scalers, MMU/dilation/connectivity fits) is fitted on **training data only**.
- Test for: target leakage, train/test contamination, duplicate leakage, geographic leakage,
  preprocessing leakage.
- Synthetic data is allowed **only** for unit tests, pipeline tests, stress tests, and edge cases,
  and must be labelled `SYNTHETIC` in filename and docstring.
- Every dataset gets a card in `docs/datasets/` with: source, licence, sample count, splits,
  class distribution, known limitations, version/date, and how it is used.

---

## 8. REPRODUCIBILITY

- Global seed set for `random`, `numpy`, `torch`, and CUDA; seed recorded in every result artifact.
- All important parameters live in `configs/*.yaml`. No magic numbers in `src/`.
- Every saved model records: weight hash, config hash, git commit, dataset version, seed.
- Every metric report includes: model, dataset, split sizes, preprocessing, hyperparameters,
  seed, metrics, training time, inference time.
- `make reproduce` (or documented equivalent) must rebuild the pipeline from a clean environment.

---

## 9. SOFTWARE QUALITY

Required: modular packages, type hints, docstrings, config management, structured logging,
explicit exception types, input/output validation (Pydantic at boundaries), unit + integration +
e2e tests.

Forbidden: giant files, duplicated logic, hardcoded paths, hardcoded secrets, hidden global state,
magic numbers, notebook-only implementations, unnecessary dependencies.

Notebooks are for exploration only. Production logic lives in `src/`.

**Disk cleanup — never blanket-delete a temp root.** Do not sweep `%TEMP%`, `$TMPDIR` or `/tmp`
wholesale. Scope every cleanup pass to explicitly named cache directories (uv, pip, and the
like), and always exclude `%TEMP%\claude\*`, which holds the harness's own task state — deleting
it destroys in-flight command output. Cleanup runs through `scripts/cleanup.py`, which enforces
both rules; ad-hoc `Remove-Item`/`rm -rf` against a temp root is not permitted.

---

## 10. PROJECT STATUS FILE

Maintain `PROJECT_STATUS.md` at repo root. Update it at the end of **every** stage:

```
LAST UPDATED: <date> — Stage <n> <name>

COMPLETED:
IN PROGRESS:
NOT STARTED:
TESTS PASSED:      <n>/<total>
TESTS FAILED:      <list>
KNOWN ISSUES:
ARCHITECTURE DEVIATIONS:   (should normally be "none")
EXPERIMENTS RUN:
BEST CURRENT METRICS:
OPEN GATES / DECISIONS AWAITING HUMAN:
NEXT STEP:
```

---

## 11. THE FOUR PROJECT GATES

The project's health is decided by four measured numbers, not by opinions.

| Gate | Stage | Number | Question it answers |
|---|---|---|---|
| **GATE 1** | S8 | Oracle symbolic accuracy | If segmentation were perfect, would this approach work at all? |
| **GATE 2** | S13 | Transfer factor = predicted / oracle | How much survives imperfect segmentation? |
| **GATE 3** | S16 | A1 falsification (blind vs VLM vs symbolic vs oracle) | Is the symbolic path actually beating the alternatives? |
| **GATE 4** | S23 | BHARAT-VAL coarse-7 mIoU | Does this transfer to India? |

At every gate: **report the number, then stop and wait for a human decision.**
Never set an arbitrary target (e.g. "we will hit 85%") before the measurement exists.

---

## 12. RESPONSE DISCIPLINE

Per stage: explain what is being built and why → implement → run tests → show real output →
analyse failures → fix → re-run → record → update `PROJECT_STATUS.md` → stop.

Do not dump thousands of lines in one response. Do not jump ahead to a later stage.
Do not skip the measurement step.
