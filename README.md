# SatQuery

**Satellite Image Question Answering.** Ask a natural-language question about a Sentinel-1/2
scene and get back an exact, auditable answer with calibrated confidence and a full execution
trace.

> *Predict what needs perception; calculate what can be calculated.*

---

## Why this design

The benchmark's ground truth was **generated from pixel-level reference maps**: presence,
per-class region counts, areas and adjacency were extracted by a program running over CORINE
land-cover rasters. The answers are measurements, not opinions.

So SatQuery reproduces that process rather than guessing its output. One segmentation model
predicts a 44-class CORINE Level-3 map; a deterministic geometry engine computes the answer
from it with `scipy.ndimage` and `skimage.measure`.

The evidence that this matters is published: a frontier model with a reported ~2 trillion
parameters scores **55.86%** on a balanced yes/no question about whether two land-cover
regions touch. `binary_dilation` computes the same relation exactly, in microseconds, given a
correct map.

The argument is not "our smaller network is smarter." It is that **once perception is
separated from deterministic spatial measurement, some tasks stop needing generative
reasoning at all**.

A second consequence matters just as much: the entire Indian domain gap concentrates into the
*one* component for which Indian pixel supervision is freely available. The geometry engine is
geography-invariant by construction — area is pixel count × GSD² in Bengaluru exactly as in
Bavaria.

**Full design:** [`docs/architecture/IMPLEMENTATION_MAP.md`](docs/architecture/IMPLEMENTATION_MAP.md)
· **Standing rules:** [`CLAUDE.md`](CLAUDE.md) · **Live status:**
[`PROJECT_STATUS.md`](PROJECT_STATUS.md)

---

## The pipeline

```
GeoTIFF(s) + question
  │
  1  VALIDATION          V1   rasterio: bands, dtype, CRS, geotransform, co-registration
  2  PREPROCESSING       P1   S1 → dB → z-score · S2 20m → 10m · band-presence mask
  3  QUERY UNDERSTANDING Q1   rules over closed templates  → M10 (TF-IDF → SVM) on failure
  4  ROUTING             R1   (intent × input) → Pydantic-validated tool plan. No LLM planner.
  5  PERCEPTION          M1 segmenter · M5 metadata · M6 change      ← the only learned vision
  6  SYMBOLIC COMPUTE    M2   aggregate → mask → components → THE NUMBER
  7  ANSWER DECISION     M3 binary · M4 MCQ · M7 VLM (language only)
  8  CONFIDENCE          M9   calibrated P(answer correct) + abstention policy
  9  ASSEMBLY            Assembler → JSON · evidence · trace · PDF
```

**The number-flow rule.** A language model may *phrase* an answer. It may never *produce the
numerical value* in it. Numbers originate in M2 and are substituted into templates. Components
exchange typed structures, never natural language.

---

## Setup

Requires [`uv`](https://docs.astral.sh/uv/). It provisions the pinned interpreter itself — no
system Python needed.

```bash
uv python install 3.12
uv sync --extra dev          # or: make setup
cp .env.example .env         # then fill in as stages require
```

Verify:

```bash
uv run python scripts/tasks.py check    # lint + typecheck + test
uv run python scripts/tasks.py test     # pytest
uv run python scripts/tasks.py lint     # ruff
uv run python scripts/tasks.py          # list all targets
```

`scripts/tasks.py` is the canonical, verified entry point. Makefile targets mirror
`scripts/tasks.py`; verified via the latter on this environment — GNU `make` was unavailable
to test directly.

---

## Layout

```
src/satquery/
  config/        typed hierarchical YAML loading (Pydantic)
  data/          dataset loading, splits, rasterio-only GeoTIFF access
  preprocessing/ P1 — sensor normalisation, augmentation
  taxonomy/      CORINE hierarchy, L3(44) → level aggregation
  geometry/      M2 — the deterministic geometry engine
  models/        M1, M3–M10
  routing/       Q1 parsing, R1 deterministic routing
  inference/     AnswerAssembler, end-to-end path
  evaluation/    oracle harness, baselines, gates, statistics
  api/           service boundary
  security/      sanitisation, injection defences, benchmark quarantine
  utils/         paths, seeding, hashing, logging, environment, run registry

configs/         project · logging · data · preprocessing · taxonomy · m1 · m2 · eval
tests/           unit · integration · model · api · e2e
reports/runs/    one directory per run: config, environment, seed, commit, metrics, logs
```

No parameter is hardcoded in `src/`. Every knob lives in `configs/*.yaml` and is validated
against a Pydantic schema that **rejects drift from the frozen architecture** — you cannot
load a config with 19 segmentation classes, 11 input channels, a random split, or mixup
enabled.

---

## Non-negotiables

These are enforced in code and in tests, not just documented.

| Rule | Enforcement |
|---|---|
| `rasterio` only for GeoTIFFs — never PIL/OpenCV/`imread` | PIL silently drops bands, rescales 16-bit, discards CRS. Areas then come out wrong by a constant factor, invisibly. |
| Benchmark split is sealed | `security/benchmark_guard.py` raises unless `ALLOW_BENCHMARK_EVAL=1`. Denied by default. |
| Geographic block CV, k=5 | Random splits leak: adjacent 1.2 km patches are spatially autocorrelated. Schema rejects `random`. |
| No mixup / cutmix | They fabricate region boundaries and change component counts, destroying the topology the symbolic path depends on. |
| Deterministic routing | No LLM planner, no `eval()`, no dynamic plugin loading. |
| Fitted geometry parameters start `null` | Connectivity, MMU, opening kernel and dilation radius are *recovered* from data at S8 — never guessed. |
| Seed everything, record everything | Every run writes config, environment, seed and commit to `reports/runs/<run_id>/`. |
| No fabricated results | If it was not run: `NOT YET VERIFIED`. If it failed: the traceback. |

---

## Stage map

Execution runs **S0–S26** (`STAGE_PROMPTS.md`). Four measured gates decide the project's
health — each reports a number and then stops for a human decision. No target is set before
its measurement exists.

| Stage | What lands |
|---|---|
| **S0** | Architecture comprehension → `docs/architecture/IMPLEMENTATION_MAP.md` ✅ |
| **S1** | Project foundation: config, logging, errors, seeding, run registry ✅ |
| **S3** | Benchmark forensics → `docs/ANSWER_GRAMMAR.md`; resolves the real task vocabulary |
| **S8** | **GATE 1 — oracle symbolic accuracy.** Zero GPU hours. The ceiling of the strategy. |
| **S13** | **GATE 2 — transfer factor.** How much survives imperfect segmentation. |
| **S16** | **GATE 3 — A1 falsification.** Blind vs VLM vs symbolic vs oracle. The exit condition. |
| **S17** | M6 change path; refit geometry parameters on predicted maps |
| **S23** | **GATE 4 — BHARAT-VAL coarse-7 mIoU.** Does it transfer to India? |

`TARGET(t) = ORACLE(t) × TRANSFER(t)` — the honest form of a target, with two measurements in
it. If the oracle is low, the answer grammar is not recovered and it is not a model problem.
If transfer is low, segmentation is binding.

**The geometry engine and the oracle experiment come before training M1.** Training first
would conflate "is the idea right?" with "is the segmentation good enough?" — and you could
not tell which was binding.

---

## Licence

Not yet determined. A licence audit of every corpus (reBEN, BigEarthNet.txt, SECOND, CDVQA,
VRSBench, the reBEN checkpoints) is scheduled for S3.
