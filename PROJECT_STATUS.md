LAST UPDATED: 2026-08-30 — Stage S1 Layer 0: Project Foundation

Stage numbering: S0–S26 (our own execution breakdown, per STAGE_PROMPTS.md). This is not the
architecture PDF's numbering — the PDF has only an 8-week plan. The two reconcile via
STAGE_PROMPTS.md Appendix B and CLAUDE.md §11.

COMPLETED:
- S0 — Architecture comprehension. docs/architecture/IMPLEMENTATION_MAP.md (11 sections):
  9-stage pipeline, component inventory, per-intent data flow with firing matrix, model/dataset
  matrix, error-propagation map, build order, testing plan, TARGET(t)=ORACLE(t)xTRANSFER(t)
  accuracy plan, risk register, assumptions, definition of done. All five S0 gate decisions
  applied and logged in §10.2.

- S1 — Project foundation. No ML logic, no dataset access, no placeholder returning a dummy
  value. All eleven deliverables:
   1. Repository structure — src/satquery/{data,preprocessing,taxonomy,geometry,models,routing,
      inference,evaluation,api,security,utils,config}; configs/; tests/{unit,integration,model,
      api,e2e}/; scripts/; data/{raw,interim,processed}/; models/; reports/{experiments,
      evaluation,error_analysis,runs}/; docs/{architecture,datasets,experiments,security}/;
      notebooks/exploration/.
   2. Dependency management — pyproject.toml, every version pinned exactly. All 13 core pins
      resolved on first sync. Nothing added beyond what the architecture justifies.
   3. Configuration — 8 hierarchical YAML files loaded into one typed Config validated by
      Pydantic with extra="forbid" and frozen=True. No parameter hardcoded in src/. The schema
      REJECTS drift from CLAUDE.md §1: 19 classes, wrong channel count, random split, and
      mixup/cutmix all fail validation.
   4. Structured logging — JSON via structlog, every record carrying run_id, stage, component,
      level and ISO-UTC timestamp, with a redaction processor applied to every field.
   5. Exception hierarchy — SatQueryError base + InputValidationError, TaxonomyError,
      GeometryError, RoutingError, ModelError, ContractViolationError, plus ConfigError
      (logged in EXPERIMENT_LOG). Structured context on every error; no bare except anywhere
      (ruff TRY/E722 enforced).
   6. Reproducibility — set_global_seed() covering random/numpy/torch/CUDA + PYTHONHASHSEED,
      returning a SeedReport of what was ACTUALLY seeded; capture_environment() recording
      python version, 13 package versions, platform, git commit + dirty flag, GPU, seed;
      hash_file() (streaming) and hash_config() (canonical, order-independent).
   7. Run registry — reports/runs/<run_id>/ with config.json, environment.json, manifest.json
      (seed, config hash, git commit, timings, failure state), metrics.json, run.log.
      Append-only: reusing a run id raises ContractViolationError.
   8. Secrets — .env.example only; python-dotenv pinned; .gitignore covers .env, data/, models/,
      checkpoints, .venv/. uv.lock is deliberately TRACKED (it is what makes reproduction real).
      Verified by git check-ignore.
   9. Testing — pytest with markers unit/integration/slow/gpu/benchmark, --strict-markers,
      coverage config. Marker selection verified (162 unit / 9 integration).
  10. CI-style checks — ruff (lint), mypy --strict (typecheck), pytest. All three pass.
  11. README.md — what the project is, why the design, setup, layout, non-negotiables, stage map.

- Bonus foundation pieces justified by the standing rules, not scope creep:
    * security/benchmark_guard.py — CLAUDE.md §7 says "Enforce this in code". Denies by
      default; only the exact string "1" opens it.
    * inference/assembler.py — AnswerAssembler, per the S0 gate naming decision (§10.2 A4).
      Raises NotImplementedError; verified it does not return a dummy value.

TESTS PASSED:      171/171
TESTS FAILED:      none
COVERAGE:          92% (484 statements, 35 uncovered). Uncovered lines are branches genuinely
                   unreachable in this environment: CUDA paths, the torch-missing fallback,
                   and git-unavailable paths.

Real pytest output (final run, 2026-08-30):
    platform win32 -- Python 3.12.13, pytest-8.3.4, pluggy-1.6.0
    collected 171 items
    tests\integration\test_run_registry.py .........            [  5%]
    tests\unit\test_benchmark_guard.py ............             [ 12%]
    tests\unit\test_config.py ....................              [ 23%]
    tests\unit\test_environment.py ..............               [ 32%]
    tests\unit\test_exceptions.py ...(61)...                    [ 67%]
    tests\unit\test_hashing.py ...........                      [ 74%]
    tests\unit\test_logging_redaction.py ...............(31)    [ 92%]
    tests\unit\test_seed.py .............                       [100%]
    ============================ 171 passed in 19.07s ============================

Two real bugs were found by these tests and fixed, not worked around:
  - The redaction path regex stopped at whitespace, so the project root
    (".../Gokul Srinivasan/...") was split mid-path: the fragment resolved outside the project
    and was redacted as external while the remainder leaked. Fixed by testing the whole string
    as a path first (exact and space-safe), with the embedded scan as fallback.
  - A bare "/" inside a RELATIVE path ("configs/m2.yaml") matched the POSIX-absolute
    alternative and was redacted. Fixed by requiring start-of-string or preceding whitespace,
    and by skipping non-absolute paths entirely.

IN PROGRESS:
- S2 — Dataset acquisition. MEASUREMENT PHASE ONLY. Nothing has been downloaded.
  Real sizes obtained from authoritative sources (Zenodo API, HF repo listing):

  reBEN / BigEarthNet v2.0 — Zenodo record 10891137, licence CDLA-Permissive-1.0
    BigEarthNet-S2.tar.zst                    63,251,710,377 B   63.25 GB
    BigEarthNet-S1.tar.zst                    54,439,153,171 B   54.44 GB
    Reference_Maps.tar.zst                       282,391,301 B  282.39 MB
    metadata.parquet                               3,616,349 B    3.62 MB
    metadata_for_patches_with_snow_cloud...          710,162 B    0.71 MB
    TOTAL                                    117,977,581,360 B  117.98 GB compressed

  BigEarthNet.txt — HF BIFOLD-BigEarthNetv2-0/BigEarthNet.txt, CDLA-Permissive-1.0, NOT gated
    BigEarthNet.txt.parquet                                       467 MB
    (repo total ~504 MB; annotations only, no imagery)
    Matches the architecture's stated ~467 MB figure exactly.

  KEY FINDING — everything through GATE 1 needs no imagery at all.
    S8 Experiment O1 feeds GROUND-TRUTH CORINE reference maps into M2, not predictions.
    S3 forensics needs the annotation parquet. S4 taxonomy needs metadata + CORINE nomenclature.
    S7 M2 needs reference maps. So S3-S8, including GATE 1, need only:
        Reference_Maps 282.39 MB + metadata 4.33 MB + BigEarthNet.txt 467 MB = ~754 MB
    The 117.69 GB of imagery is first required at S11/S12 (M1 smoke test and training) —
    exactly where the deferred cloud GPU+disk decision already applies.

  BLOCKER FOR IMAGERY SUBSETTING (reported, not worked around):
    Zenodo serves reBEN imagery as MONOLITHIC .tar.zst archives with no per-patch HTTP access.
    A stratified subset of the IMAGERY therefore cannot be selectively downloaded — it would
    require pulling all 117.69 GB first. Reference maps CAN be subset, because tar supports
    selective extraction and zstd supports streaming.
    The HF API returned HTTP 401 unauthenticated for every reBEN mirror probed, so a
    shard-accessible mirror could not be confirmed without an HF token.

NOT STARTED:
- S2 download execution (awaiting approval of the subset plan below).
- S3 onward. No model trained, no metric measured.

KNOWN ISSUES:
- MAKEFILE TARGETS ARE NOT YET VERIFIED. The Makefile is written with the required lint/
  typecheck/test targets, but GNU make is not installed on this machine (make, mingw32-make,
  gmake, nmake all absent), so `make test` has never been executed here. A dependency-free
  equivalent, scripts/tasks.py, runs the identical commands and IS verified:
  `uv run python scripts/tasks.py check` runs ruff + mypy + pytest, all passing.
  Logged in EXPERIMENT_LOG.md.
- `make reproduce` intentionally exits non-zero with an explanatory message. There is no
  pipeline to reproduce as of S1, and a target that printed success would be a fake result.
- (resolved) STAGE_PROMPTS.md is now committed and has been read in full (1,558 lines). Every
  S-anchor used at the S0 gate is confirmed correct, and Appendix B's week mapping is recorded
  in IMPLEMENTATION_MAP §10.2 A2. Assumption A2 is CLOSED.
- docs/architecture/ holds "SatQuery_Architecture (1) (1).pdf" while CLAUDE.md §0 names
  "SatQuery_Architecture.pdf". Content verified as Architecture B. Recommend renaming.
  (§10.2 A11)

ENVIRONMENT FINDINGS (surfaced during S1 — these constrain LATER stages, not this one):
- NO PYTHON WAS INSTALLED on this machine. The python.exe on PATH was the Microsoft Store
  stub and py.exe reported none installed. Resolved by provisioning CPython 3.12.13 via uv.
- NO NVIDIA GPU IS VISIBLE. nvidia-smi is absent and torch.cuda.is_available() is False, so
  torch 2.5.1 is running CPU-only. The architecture assumes a single 24 GB GPU for M1/M6/M7.
  Every seeding and environment test reports this honestly rather than assuming a device.
  A GPU must be secured before S13 (M1 training). IMPLEMENTATION_MAP §9.6 records "GPU not
  secured early" as the documented trigger to fall back to Architecture C.
- DISK IS AT 98% — 6.6 GB free on C: before the environment install, ~5.5 GB after. reBEN is
  549,488 patches and BigEarthNet.txt is a ~467 MB parquet plus imagery; the full corpus does
  not fit. Storage must be resolved before S2/S3 begin downloading anything.

ARCHITECTURE DEVIATIONS: none

EXPERIMENTS RUN: none (no measurement stage has been reached)

BEST CURRENT METRICS: none — no gate has been reached. Per CLAUDE.md §11, no target exists
until the corresponding measurement exists.

OPEN GATES / DECISIONS AWAITING HUMAN:
- None blocking S2. S1 is complete with all tests green.

STANDING ITEM — COMPUTE + FULL-CORPUS STORAGE (decided 2026-08-30, deferred to before S12)
  GPU compute for M1/M6/M7 training (S12+) — not yet secured, decision deferred to before S12,
  likely resolved via rented cloud GPU instance rather than local hardware.

  Full-corpus storage is merged into this same decision. We do NOT provision storage for the
  full 549,488-patch reBEN corpus now; it is to be solved together with the GPU via a rented
  cloud GPU+disk instance rather than local expansion, and likewise deferred to before S12.

  Consequences accepted:
    * S2–S11 proceed CPU-only, on a stratified geographic dev subset sized to local disk.
    * Per STAGE_PROMPTS.md S2, all HEADLINE results must eventually come from the full split,
      never from the dev subset. The subset is for iteration only.
    * Do NOT re-raise either half of this as a Gate Report before S12 unless something changes
      (e.g. the dev subset proves too small to fit local disk, or a gate measurement is found
      to depend on full-corpus scale).

  Carried forward as ASSUMPTION — REQUIRES VALIDATION (IMPLEMENTATION_MAP §10.2), each with
  an owning stage, none blocking now:
    A1  mandatory capabilities taken from the architecture document (defined §11.0)
    A2  CLOSED at S1 — STAGE_PROMPTS.md committed, read, and all S-anchors verified
    A3  M6 live-inference input vs SECOND/CDVQA training data — resolve at S17
    A5  real task vocabulary (8-way vs 10-way vs 15 tasks) — resolve at S3
    A6  does area exclude MMU-dropped components — resolve at S8
    A7  is M5 wired into the caption path — resolve at S8
    A8  how M3/M4 map onto CDVQA's closed 19-category answer set — resolve at S17
    A9  exact European-mIoU stop-rule threshold — before S23
    A10 Köppen zone class count k — resolve at S3
    A11 PDF filename does not match CLAUDE.md §0

NEXT STEP:
- Proceed to Stage S2 per STAGE_PROMPTS.md, after resolving the storage question above if S2
  touches data.
- Ordering constraint stands (IMPLEMENTATION_MAP §6.2): the M2 geometry engine and the oracle
  experiment (GATE 1, S8) precede any M1 training. S3 benchmark forensics precedes both and
  closes the largest cluster of open assumptions.
