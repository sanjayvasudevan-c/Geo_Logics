LAST UPDATED: 2026-08-30 — Stage S3 Benchmark Forensics COMPLETE (4 gates approved)

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
   9. Testing — pytest with markers unit/integration/model/slow/gpu/benchmark, --strict-markers,
      coverage config. Marker selection verified (162 unit / 9 integration).
  10. CI-style checks — ruff (lint), mypy --strict (typecheck), pytest. All three pass.
  11. README.md — what the project is, why the design, setup, layout, non-negotiables, stage map.

- Bonus foundation pieces justified by the standing rules, not scope creep:
    * security/benchmark_guard.py — CLAUDE.md §7 says "Enforce this in code". Denies by
      default; only the exact string "1" opens it.
    * inference/assembler.py — AnswerAssembler, per the S0 gate naming decision (§10.2 A4).
      Raises NotImplementedError; verified it does not return a dummy value.

TESTS PASSED:      188/188 (+1 skipped non-Windows, +1 slow deselected)
TESTS FAILED:      none
COVERAGE:          92% (484 statements, 35 uncovered). Uncovered lines are branches genuinely
                   unreachable in this environment: CUDA paths, the torch-missing fallback,
                   and git-unavailable paths.

Real pytest output (final run, 2026-08-30, Stage S2):
    platform win32 -- Python 3.12.13, pytest-8.3.4, pluggy-1.6.0
    collected 190 items / 1 deselected / 189 selected
    tests/integration/test_run_registry.py .........            [  4%]
    tests/unit/test_benchmark_guard.py ............             [ 11%]
    tests/unit/test_cleanup_guardrail.py ...........            [ 16%]
    tests/unit/test_config.py ....................              [ 27%]
    tests/unit/test_environment.py ..............               [ 34%]
    tests/unit/test_exceptions.py ...(61)...                    [ 67%]
    tests/unit/test_hashing.py ...........                      [ 73%]
    tests/unit/test_keepawake.py ......s                        [ 76%]
    tests/unit/test_logging_redaction.py ...............(31)    [ 93%]
    tests/unit/test_seed.py .............                       [100%]
    ========== 188 passed, 1 skipped, 1 deselected in 7.49s ==========
  The 1 deselected is the opt-in slow keepawake duration test; the 1 skipped is a
  non-Windows-only assertion. Coverage figure below predates S2 and is not re-measured.

Two real bugs were found by these tests and fixed, not worked around:
  - The redaction path regex stopped at whitespace, so the project root
    (".../Gokul Srinivasan/...") was split mid-path: the fragment resolved outside the project
    and was redacted as external while the remainder leaked. Fixed by testing the whole string
    as a path first (exact and space-safe), with the embedded scan as fallback.
  - A bare "/" inside a RELATIVE path ("configs/m2.yaml") matched the POSIX-absolute
    alternative and was redacted. Fixed by requiring start-of-string or preceding whitespace,
    and by skipping non-absolute paths entirely.

SLEEP PREVENTION — VERIFICATION STATUS (asked for explicitly; recorded so S12 can rely on it)
  MECHANISM: src/satquery/utils/keepawake.py — SetThreadExecutionState with
  ES_CONTINUOUS | ES_SYSTEM_REQUIRED, process-scoped, released on exit including on crash.
  No change was made to the user's power scheme.

  STATUS: **VERIFIED IN PRODUCTION CONDITIONS, WITH AN A/B CONTROL.** This is stronger than
  "the API returned success" and stronger than a synthetic hold test.

    Machine is on AC mains (Win32_Battery BatteryStatus=2), so the idle-sleep threshold is
    600 s. Verified from the same Windows System event log used to diagnose the original kill.

    CONTROL (no keepawake): extraction run killed by Modern Standby. Event log shows
      "The system is exiting Modern Standby" 06:50:09 and "Wake from sleep detected" 06:50:13.
    TREATMENT (keepawake active): a single continuous extraction pass of 616.9 s — PAST the
      600 s threshold — completed successfully. Across the whole 06:50 to 07:32 window
      (~42 min) the System log records ZERO events of id 42/107/506/507.

    Same workload, same disk I/O, same absence of user input. The only difference was the
    power request. Disk activity alone does not explain it: the control run was doing identical
    continuous I/O and still slept.

  RESIDUAL UNCERTAINTY (stated rather than glossed): `powercfg /requests` requires an elevated
  prompt and is unavailable here, so Windows' registration of the request was never observed
  directly. The evidence is behavioural, not introspective.

  RE-VERIFICATION ON NEW HARDWARE: tests/model/test_keepawake_duration.py holds the request for
  660 s and asserts no standby event fires. Marked `slow` and DESELECTED by default (pytest
  addopts carries -m 'not slow'). Run it explicitly before S12 on whatever machine trains M1:
      uv run pytest -m slow
  It has NOT been run on this machine — the production A/B above supersedes it here.

IN PROGRESS:
- S2 — Dataset acquisition. ACQUISITION COMPLETE for the non-imagery tier; card written.
  Remaining S2 items: dataset cards for SECOND/CDVQA/VRSBench/RSVQA (not yet acquired),
  and closing the eight NOT YET VERIFIED licences in docs/datasets/LICENCE_AUDIT.md.

  ACQUIRED AND VERIFIED:
    reBEN core, 287 MB, all md5-verified against the Zenodo manifest
      metadata.parquet 3,616,349 B / snow-cloud parquet 710,162 B
      Reference_Maps.tar.zst 282,391,301 B
    BigEarthNet.txt 466,819,745 B, sha256-verified, pinned to revision 72d865f2
    Imagery (117.69 GB) NOT fetched — fetch_reben.py refuses it as tier=deferred.

  EXTRACTED (docs/datasets/reBEN_dev_subset.md):
    549,488 reference maps, 54 tile shards, 533,265,639 B logical, complete=true,
    0 patch ids without a parsable tile.

  *** COUNT CORRECTION — the archive is exhaustive, and my projection was wrong. ***
    I planned against metadata.parquet's 480,038 patches. The archive actually holds a
    reference map for ALL 549,488 reBEN patches, including the 69,450 screened out for
    snow/cloud/shadow. That is 14.5% more than projected. Anyone sizing storage from
    metadata.parquet will under-count by the same margin.

  *** CORRECTED PER-MAP STORAGE FIGURES (use these for S12 re-projection) ***
    logical                    970.5 B/map   (exact, from the manifest)
    ALLOCATED                ~4,621 B/map    (measured on the final 139,488-map pass)
    slack factor              ~4.76x         (small files on NTFS 4 KiB clusters)
    total store, on disk      ~2.54 GB
    The earlier 3,670 B/map came from a FLAT-directory probe and under-projected the store
    by ~25%: the sharded layout adds per-directory metadata and MFT growth a flat probe
    does not capture. Measure in the target layout, not a flat one.

  MANIFEST BUG FOUND AND FIXED: on a resumed run the free-space delta covers only the maps
    written that pass, but it was being divided by the TOTAL count, under-reporting per-map
    cost. Fields renamed to allocated_bytes_this_run / bytes_per_map_allocated_this_run /
    estimated_total_allocated_bytes.

  DISK: 2.89 GB free. Total S2 footprint ~3.3 GB against the ~2.0 GB originally budgeted —
    the overage was disclosed and approved before the resume, and is explained by the 549,488
    vs 480,038 count correction plus the sharded-layout slack above.

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
- S3 onward. No model trained, no metric measured.
- Imagery acquisition (117.69 GB) — deferred to the cloud instance before S12.

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

NAMED PREREQUISITES FOR LATER STAGES (logged at S3 close-out — these are BLOCKERS, not notes)

  *** S15 IS BLOCKED — do not start until this is resolved ***
    QUESTION: does the evaluation harness supply country / season / climate_zone / latitude /
      longitude alongside the image AT INFERENCE TIME?
    WHY IT BLOCKS: the entire M5 gate-check depends on it. If the harness supplies them, the
      metadata MCQs are lookups and M5 is discarded; if not, they must be predicted from pixels
      and M5 is a first-class model. S15 cannot evaluate its own gate without this answer.
    WHAT WOULD SETTLE IT: the harness/submission specification, or an official baseline's input
      signature. The parquet CANNOT answer it — this is a property of the eval protocol.
    STATUS: INCONCLUSIVE as of S3. Owner: human.
    NOTE: independent of this, the three columns are PERMANENTLY BANNED as model input
      features — see CLAUDE.md §7. That ban holds whatever S15 decides.

  *** S14 PREREQUISITE — M3 confidence gate (condition (b) on GR-4, binding) ***
    The deterministic comparator path MUST NOT be binary match/no-match. It must fall through
    to the learned M3 path whenever the parse is ambiguous, low-confidence, or matches no known
    comparator form. It must NEVER guess and silently return a comparator result.
    Required: (1) parser abstains rather than guessing; (2) ambiguity made explicit — multiple
    comparators matched, no threshold parsed, >1 class name present (53,261 such rows appeared
    in S3's own analysis, so this is frequent), or a residual form; (3) the chosen path is
    recorded in the execution trace and the deterministic/learned/abstained split is REPORTED
    as a measured rate; (4) S8 measures oracle accuracy of the deterministic path PER COMPARATOR
    FORM — anything below ~100% on ground-truth maps means the parser is wrong, not the model.
    Condition (a) — the regex re-pass — is DISCHARGED, see below.

  *** S7 PREREQUISITE — confirm the decile boundary rule against computed truth ***
    S3 resolved the DIRECTION from released answers (standard semantics: >= and <= include the
    boundary; > and < exclude it) — 158 decisive groups of 147,953 observed. But 33.9% of
    contradictory pairs are parse artifacts, so confidence is MODERATE, not settled.
    configs/m2.yaml bin_boundary_rule is deliberately null. S7 must confirm once the S4 L3->19
    aggregation table makes true coverage computable.

  *** S8 PREREQUISITE — check whether CAPTIONS follow the arXiv:2603.29630 §3.1 pipeline ***
    VQA/MCQ demonstrably do NOT (they are decile-quantised). But caption ANSWERS contain
    square_metres (42,036) and thousand_m2 (41,987) patterns, so the caption path may retain the
    finer 1,000 m2 convention. NOT resolved at S3 — deliberately left to S8's caption oracle,
    which is the right place to measure it. Do not assume the VQA finding generalises.

  *** S26 PREREQUISITE — adjacency framing ***
    See IMPLEMENTATION_MAP §1.4 boxed warning. The judge pack must NOT claim "beats a 2T-param
    model on adjacency" without the majority-baseline number beside it: the adjacency prior is
    57.1% "no", which already exceeds the 55.86% frontier-model figure.

S3 GATE REPORTS — ALL FOUR APPROVED 2026-08-30. See reports/experiments/GATE_REPORT_S3.md §14
  All four contradict named architectural decisions. Root cause: the architecture's
  answer-grammar assumptions were generalised from the CAPTIONING pipeline described in
  arXiv:2603.29630 §3.1; the VQA/MCQ annotations do not follow it.

  GR-1  Questions use the 19-CLASS VOCABULARY, not CORINE L3.
        Evidence: 19/19 mcq/presence options inside the 19-class set, 0 outside (1,227,849
        rows). No CLC L1 name appears; every apparent L2/L3 hit is a substring of a 19-class
        name. CLAUDE.md §1 calls the 19-class scheme "image-level multi-label only, NOT the
        segmentation target".  Recommendation: keep M1 at L3-44, make the S4 aggregation
        table target L3->19, promote the 19-class head onto the query path.
        Affects: M1 head, M2 aggregation, S4.

  GR-2  Area is DECILE-QUANTISED (11 bins, 144,000 m2 granularity), not continuous rounded
        to 1,000 m2. configs/m2.yaml area_rounding_m2=1000 is 144x too fine.
        Evidence: m2 n=114,091 with 11 distinct values, gap min=median=mode=144,000;
        percent n=227,749 with 11 distinct values 0,10,...,100. 1,440,000 m2 = whole patch.
        S7 IMPACT (asked explicitly): the area ROUNDING sweep becomes moot, but a NEW
        fittable parameter replaces it — the decile BOUNDARY convention, because 68.2% of
        adjacent MCQ area ranges share an endpoint. connectivity / MMU / opening kernel /
        adjacency dilation sweeps are ENTIRELY UNAFFECTED and remain S7's highest value.
        Affects: M2, S7.

  GR-3  M4 distance metric — full CLAUDE.md §6 change-control block in the gate report.
        MCQ distractor spacing is ADDITIVE on an 11-point decile grid, contradicting M4's
        specified LOG scale for area. Options are 100% ranges (173,684/173,684), never
        point values. Proposed: range-containment test + decile-index fallback; count
        stays integer difference. Softmax/T retained so M9's interface is unchanged.
        DECISION: WAITING FOR APPROVAL.

  GR-4  M3 structure — full CLAUDE.md §6 change-control block in the gate report.
        Binary questions are DETERMINISTIC threshold/range comparisons, contradicting
        REV F3's VERIFIED claim that NO answers are near-misses needing a learned boundary.
        Evidence: >=72.3% of binary area and >=88.4% of binary count questions are explicit
        comparators; measured |stated-true| for NO answers is near-uniform (p25=20,
        median=40, p75=60 pts), not a concentrated near-miss band.
        Proposed: two-path M3 — deterministic comparator path for the parseable majority,
        retain the specified LightGBM/logistic head for the residual.
        RISK FLAGGED HONESTLY: 27.7% of area and 11.6% of count forms were unmatched by the
        comparator regex, so the deterministic share is a LOWER BOUND; a parser misparse
        silently flips an answer with no model to absorb it.
        DECISION: WAITING FOR APPROVAL.

  APPLIED AT CLOSE-OUT:
    * configs/m2.yaml — area_rounding_m2 REMOVED; replaced by area_bins=11,
      patch_area_m2=1440000, bin_boundary_rule=null (confirmed at S7). Schema follows;
      a test asserts the boundary rule stays null rather than being guessed.
    * CLAUDE.md §7 — permanent ban on country/season/climate_zone as model input features.
    * IMPLEMENTATION_MAP §1.4 — boxed adjacency framing warning, binding on S8/S16/S26.

  GR-4 condition (a) DISCHARGED — the unmatched binary forms are PHRASING, not different
  answer logic. A widened comparator set cut the residual from 27.7%->21.66% (area) and
  11.6%->7.77% (count), and every high-frequency remainder is comparator-equivalent:
  complement questions ("Is there some part not covered by X?" == coverage<100%) and
  singularity/plurality questions ("only a single continuous region?" == count==1;
  "multiple continuous areas?" == count>=2). So M3's two-path design stands and its
  deterministic share is a LOWER bound.

  NOT blocked: S7's connectivity, MMU, opening-kernel and adjacency-dilation sweeps are
  unaffected by all four findings and remain S7's highest-value work.

S3 FINDINGS THAT ARE NOT GATES:
  * M5 IS NOT DISCARDABLE. country/season/climate_zone are 100.00% identical to the correct
    MCQ answer (35,561/35,561; 35,561/35,561; 35,562/35,562) — they are LABELS, not inputs.
    Using them to answer the metadata MCQs is circular leakage. INCONCLUSIVE whether the
    eval harness supplies them as input at inference; needs the harness spec.
  * ANSWER PRIORS: binary presence/area/count balanced 50.0/50.0; all 8 MCQ sub-tasks within
    0.7 pts of 25%. ONE EXCEPTION: binary/adjacency is 57.1% no / 42.9% yes — so answering
    "no" to every adjacency question scores 57.1%, ABOVE the 55.86% a reported-2T-parameter
    model achieves. Must be reported at S8 and S16; it reframes the headline comparison.
  * Referring qualifiers: exactly {largest, smallest} x 8 surface phrasings; ~55% of
    referring expressions carry no qualifier.
  * Adjacency dilation convention: INCONCLUSIVE from phrasing (9 synonyms, no numeric
    qualifier). Only the S7 sweep can recover it — unchanged from plan.

- S1/S2 have no open gates.

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
