LAST UPDATED: 2026-08-31 — CF-5 RESOLVED (option A adopted). 555 tests pass, suite GREEN.
GATE 1 NOW STANDS AT 92.78% strict / 96.93% attempted / +43.70 headline gap.
NEXT: S10 — R1 deterministic router + typed contracts + scene cache. IN PROGRESS.

=== CARRIED FORWARD — KEEP VISIBLE UNTIL CLOSED ===

CF-5  GATE 1 OF RECORD WAS STALE — *** RESOLVED 2026-08-31, option A adopted. CLOSED. ***
      Gate 1 re-run and the new measurement adopted: 92.78% strict / 96.93% attempted /
      +43.70 gap, stamped with config fingerprint e4dd82df6b4f309f. The abstention gap is now
      4.15 points (see CF-1). GATE1_oracle.md §8 records the drift and its cause in full; §1-§6
      still hold the original 87.11% the PASS verdict was given on, and §7 still isolates the
      S7 addendum, so each step is attributable rather than merged. Provenance guard is GREEN.
      Prior state, kept for the record:
      A shared config moved a GATE number with nobody re-running the gate and nothing failing.
      configs/synonyms.yaml is used by BOTH routing/parser.py (Q1) and evaluation/oracle.py.
      S9 added two missing surface forms for the PARSER's benefit — the plural "lands
      principally occupied by ..." and the singular "agro-forestry area". Those also improved
      the ORACLE's class resolution.

      MEASURED (validation, n=300/task, identical protocol):
                            recorded    today     delta
        oracle_strict         90.15%   92.78%    +2.63
        oracle_attempted      96.92%   96.93%    +0.01
        best_blind            49.07%   49.07%     0.00
        headline gap         +41.07   +43.70     +2.63
        ABSTENTION GAP          6.77     4.15     -2.62

      Isolated: configs/synonyms.yaml is the ONLY fingerprinted file the S9 commit touched;
      oracle.py, geometry/ and taxonomy/core.py were untouched. So the whole +2.63 is that
      one config edit.

      THE RECORDED NUMBER HAS NOT BEEN OVERWRITTEN. reports/evaluation/gate1_oracle.json still
      holds the 90.15% measurement and is now stamped with the config fingerprint it was
      ACTUALLY measured under (d36320c50b555676, recovered from git at 8a848ef). The re-run is
      preserved separately as gate1_oracle_S9_DRIFT.json. GATE1_oracle.md is unchanged.

      DECISION NEEDED — either:
        A) adopt the new measurement: re-run run_oracle.py + write_gate1_report.py, and Gate 1
           becomes 92.78% strict / +43.70 gap. Cost: minutes. The number moves UP and the cause
           is understood and legitimate (better class resolution, no leakage).
        B) revert the synonym additions — NOT viable, Q1 depends on them.
      Recommendation: A. It is not a re-litigation of the gate verdict, which was PASS on a
      number that has since improved.

      STRUCTURAL FIX ALREADY SHIPPED so this cannot recur silently:
        * src/satquery/evaluation/provenance.py — config_fingerprint() over the three configs
          that can move a measured number (synonyms, m2, taxonomy).
        * run_oracle.py now stamps _provenance into every gate artifact.
        * tests/unit/test_gate_provenance.py — FAILS when a recorded gate no longer matches the
          working tree. IT IS FAILING RIGHT NOW, AND THAT FAILURE IS THE FINDING, NOT A BUG.
          Do not edit it to pass. It also carries a can-it-fire guard (CLAUDE.md §5 corollary).

CF-1  PARSER-ABSTENTION GAP — **S9's explicit target.** OPEN.
      Gate 1 strict 87.11% vs attempted 93.89% = a 6.78-point gap that is ENTIRELY parser
      abstention, not geometry. After the S7 addendum the same gap is 90.15% vs 96.92% =
      6.77 points. It is the cheapest accuracy in the project because the geometry behind it
      is already correct. Known composition, measured at S8 (n=300/task, validation):
        binary|area       21.3% abstain — 'no threshold' 24, 'no comparator' 24, 'no class' 16
        mcq|adjacency     20.3% abstain — all 'no MCQ option yielded two classes'
        mcq|area          11.3% abstain — 'no class name resolved'
        binary|count       7.3% abstain — mostly 'no class name resolved'
        binary|adjacency   2.3% abstain — 'adjacency needs two classes'
      NOTE the shape of this: the dominant cause across five task types is CLASS RESOLUTION
      and OPTION SPLITTING, not comparator vocabulary. S9's parser should be measured against
      that breakdown, not against a generic coverage number.

      >>> S9 UPDATE — STILL OPEN, and it is worth being exact about why.
      >>> S9 built Q1 (src/satquery/routing/parser.py), which reaches 99.60% coverage on a
      >>> held-out validation slice. But GATE 1's abstentions were produced by a DIFFERENT
      >>> module — satquery/evaluation/oracle.py's S8 answer producer — so the 6.77 points do
      >>> NOT close automatically, and claiming otherwise would be a false close.
      >>> What IS established: the Gate 1 abstention causes are the same defect classes Q1
      >>> just fixed and now has tests for —
      >>>    'no class name resolved' -> the `sea`-inside-"season" substring bug, the missing
      >>>                                comma variants, and the missing plural "lands ..."
      >>>    'no threshold'           -> `m^2` was never matched (109 of 333 sampled spellings)
      >>>    'no MCQ option yielded two classes' -> options were never searched for the pair
      >>> So the fix is to route the oracle through Q1 rather than to re-derive it. That is a
      >>> real change to how a GATE number was produced, so it is NOT being done silently here.
      >>> Proposed home: S13, where predicted maps are scored end-to-end and the oracle is
      >>> re-run anyway. Flagging now so it is a decision, not a discovery.

      >>> MEASURED AT S9-CLOSE (scripts/diagnose_abstention_gap.py,
      >>> reports/experiments/cf1_abstention_diagnostic.json). Traceable, not inferred:
      >>>
      >>>   original gap (recorded Gate 1)                     6.77 points
      >>>   ALREADY CLOSED, as a side effect of S9's synonyms.yaml edit   -2.62 points
      >>>   -> gap measured with today's code                   4.15 points   <-- CURRENT
      >>>
      >>> Of the 116 remaining oracle abstentions over 2,700 validation items, Q1 supplies the
      >>> missing field for 65 of them = 56.0%:
      >>>     no MCQ option yielded two classes    61 abstentions, Q1 fixes 58  (95.1%)
      >>>     area question with no comparator     25 abstentions, Q1 fixes  7  (28.0%)
      >>>     area question with no threshold      27 abstentions, Q1 fixes  0
      >>>     count question with no comparator     3 abstentions, Q1 fixes  0
      >>>   'no class name resolved' has DISAPPEARED entirely — that whole category is what the
      >>>   synonyms.yaml edit already closed.
      >>>
      >>>   -> ESTIMATED further recoverable by routing the oracle through Q1: ~2.3 points
      >>>   -> ESTIMATED irreducible without new parser work:                  ~1.8 points
      >>>
      >>> THE ~2.3 IS AN ESTIMATE, NOT A MEASUREMENT. It says Q1 supplies the missing FIELD; it
      >>> does not say the resulting ANSWER is correct. Gate 1 was NOT re-run to produce it.
      >>> The dominant single win is mcq|adjacency's option-pair splitting (58 of 65).

CF-2  M8 BUILD AUTHORIZATION — CONFIRMED STILL LIVE, NOT LOST. Queued for its own stage.
      GATE: caption BLEU-4 = 15.35 -> **BUILD M8**, inside the 10-35 band the architecture
      predicted. Measured at S8 (O2 caption oracle, 220 captions); see GATE1_oracle.md §5.
      15.35 is a LOWER bound — brevity penalty is still 0.4911, so a richer template scores
      higher. M8 = Flan-T5-base (250M) or Qwen2.5-0.5B-Instruct LoRA, per CLAUDE.md §1, and
      it is a template->style REWRITER only: CLAUDE.md §2 forbids it producing any number.
      Do not re-litigate this gate; it is decided. Just build it when its stage arrives.

      >>> S9-CLOSE STATUS: QUEUED, NOT BUILT, NOT DROPPED. No M8 code exists yet and none was
      >>> expected at S9 — S9's scope was Q1 + M10 only. The authorization stands unchanged and
      >>> unconsumed. Nothing in S9 touched it. Next relevant stage per the build order.

CF-4  DUPLICATE LEAKAGE IN QUESTION TEXT — NEW at S9, open. See DECISIONS.md D-S9-3.
      MEASURED: 31.53% of sampled validation questions appear VERBATIM in the training sample;
      for the parser residue it was 38.94%. S3's ~220,840 distinct `input` strings are spread
      over 7,128,971 rows, so text repeats heavily. The S6 geographic folds separate PATCHES,
      not question STRINGS, so this hazard is not covered by existing splitting.
      Binding on any future component trained on question text — M10 here, M8's stylizer later:
      report the verbatim-in-train and unseen-text halves SEPARATELY. An early M10 run scored a
      clean 100.00% over 719 items that was partly string memorisation.

CF-3  TEST-COVERAGE AUDIT — opened 2026-08-30 at the reviewer's direction after the
      S7 addendum showed oracle.py had shipped two independent defects with ZERO unit tests.
      Ran `pytest --cov` across the whole package rather than waiting for S24. TOTAL 72%.
      Modules materially below the line:
        evaluation/harness.py      **0%**  <-- see below, this one is not like the others
        data/download.py             0%    (S2 one-shot acquisition script, already run)
        inference/assembler.py       0%    (stub, no logic yet — S10+)
        evaluation/oracle.py        37%    (was 0%; the S7 addendum covered the direction path
                                            only. The remaining 63% is the S8 answer producer,
                                            which S9 is about to replace/extend anyway.)
        evaluation/forensics.py     40%    (the quarantine GUARD is tested; the row-group
                                            iteration paths are not)
        taxonomy/core.py            76%
      ** harness.py at 0% is qualitatively different from the rest and is being closed in S9,
      not deferred. ** It is the module that computed EVERY Gate 1 number — strict vs attempted
      accuracy, abstention accounting, and the bootstrap CI that resamples over patches rather
      than annotations. An off-by-one in its percentile index would have put a wrong confidence
      interval on every row of the gate report with nothing to catch it. A module that produces
      gate numbers must not be the least-tested module in the package.
      >>> CLOSED at S9: tests/unit/test_harness.py, 17 tests. Includes a property test that
      >>> CLUSTERED patches must yield a WIDER interval than independent ones — if that ever
      >>> reverses, the resample has silently gone back to annotation level and every gate CI
      >>> is too tight. The rest of CF-3 remains open for the S24 audit.

CF-6  S10 SUB-TASK — ROUTER MUST TRIGGER/VERIFY M10 REGENERATION, NOT LOAD-OR-CRASH. OPEN.
      Named explicitly so it is not implicitly assumed done between now and S10.
      The fitted M10 artifact is GITIGNORED (.gitignore:67 `models/*`), so a clean checkout has
      models/m10/m10_intent_svm.joblib absent. Correct for model weights, but it means R1's
      fallback path has nothing to load on a fresh clone, and CLAUDE.md §8 requires
      `make reproduce` to rebuild the pipeline from a clean environment.
      REQUIRED at S10, all three:
        (a) on a missing artifact the router REGENERATES it (or emits an actionable instruction
            naming the exact command), rather than raising an opaque load error;
        (b) it VERIFIES the loaded artifact's train_split_hash against the current training
            split, so a stale model fitted on different data cannot be loaded silently — the
            manifest already records the hash, nothing reads it back yet;
        (c) a test that DELETES the artifact and asserts the router still comes up.
      Note this is the same failure class as CF-5: an artifact whose provenance is recorded but
      never checked. The provenance module added at S9-close is the natural place to hang (b).

=== END CARRIED FORWARD ===

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

S5 — V1 INPUT VALIDATION + SENSOR PREPROCESSING COMPLETE & APPROVED. 325 tests total.

  TWO REVIEW FIXES APPLIED AT CLOSE-OUT (both root causes, not symptoms):

  R1. BAND-PRESENCE MASK — a missing binding function, not just a weak test.
      stack_channels() and band_presence_mask() were independent calls, so a caller could
      build a tensor with B11 zeroed and a mask claiming B11 present, and NOTHING would catch
      the contradiction. That failure survives review and CI and only surfaces as a corrupted
      training run — the loss still descends, the model still trains, it just learns the wrong
      thing from contaminated inputs.
      FIX: PreprocessedInput + preprocess(), which DERIVE presence from the same information
      that fills the tensor. Drift is now structurally impossible, not merely discouraged.
      The test now asserts the real claim on the tensor a forward pass receives:
      "measured but genuinely dark" and "never measured" produce BYTE-IDENTICAL 12-channel
      tensors, and only the mask recovers the difference.

  R2. SYNTHETIC LABELLING — CLAUDE.md §7 was followed by habit, not checked.
      Spot-check found test_taxonomy.py fabricating CORINE class maps with ZERO labelling.
      FIX: escalated from documented to tested (same move as the rasterio-only grep).
      tests/unit/test_synthetic_labelling.py detects fabricating modules and asserts each
      declares SYNTHETIC, that the raster factory is filename-labelled, and that all GeoTIFF
      creation stays in that one labelled place. Carries a guard against the detector matching
      nothing and passing vacuously — it caught ITSELF on first run.

  METHOD NOTE CARRIED FORWARD: for every subsequent stage, ask of each test "does this assert
  the REAL claim, or something adjacent to it?" Both R1 and R2 were found that way.
  BUILT:
    src/satquery/data/validation.py    — V1: rasterio-only, typed InputManifest or a typed
      InputValidationError whose `check` field names the exact failed check. Never coerces a
      broken input into a best-effort manifest.
    src/satquery/preprocessing/bands.py    — the FROZEN 12-channel order, asserted by test.
    src/satquery/preprocessing/sensors.py  — linear->dB, bilinear 20m->10m, z-score,
      band-presence mask, spectral indices (off by default).
    src/satquery/preprocessing/norm_stats.py + scripts/data/compute_norm_stats.py
      — training-split-only statistics with split_hash and n_samples recorded.

  *** S12 IS BLOCKED ON REAL NORMALISATION STATISTICS — NAMED BLOCKER, NOT A NOTE ***
    S11 may proceed: building M1 and smoke-testing it against synthetic/placeholder
    normalisation is legitimate, because a smoke test checks that the graph runs and the loss
    descends, not that the numbers mean anything.
    S12 MUST NOT PROCEED. Real training against placeholder statistics silently miscalibrates
    every input the model ever sees, and the damage is invisible — the loss still descends.
    DO NOT ASSUME S11's SYNTHETIC-DATA PASS MEANS S12 IS UNBLOCKED. It does not.
    To unblock S12: obtain imagery (the 117.69 GB deferred tier), then run
      uv run python scripts/data/compute_norm_stats.py --imagery-root <dir>
    and confirm configs/norm_stats.yaml exists with split: train and a recorded split_hash.

  *** NOT YET VERIFIED — REAL NORMALISATION STATISTICS DO NOT EXIST ***
    configs/norm_stats.yaml has NOT been generated. compute_norm_stats.py requires imagery,
    which is the 117.69 GB deferred tier (standing decision, before S12). The script REFUSES
    to run on any split other than 'train' and exits non-zero without imagery rather than
    emitting fabricated numbers. Every preprocessing test uses SYNTHETIC data with known
    values, so they test arithmetic correctness, not real-data behaviour.
    CONSEQUENCE: the preprocessing path is correct but UNCALIBRATED. It cannot be run on real
    reBEN imagery until the imagery lands. This is a prerequisite for S11/S12, alongside GPU.

  DESIGN POINTS WORTH KNOWING:
    * SAR zero/negative power is FLOORED to -50 dB and the floored-pixel COUNT is returned,
      not hidden. NaN/inf in the INPUT raises rather than propagating — a corrupt product is
      reported, not silently repaired.
    * Band-presence mask is a length-10 first-class input, tested to prove a dropped band is
      distinguishable from a genuinely dark one (zeros alone cannot say "not measured").
    * 60 m bands (B01/B09/B10) are absent from the frozen order by construction; a test
      asserts they can never appear in the 12-channel output.
    * GeoTIFF metadata tags are sanitised at the V1 boundary (control chars stripped, length
      capped) because they reach the query parser — a prompt-injection surface.
    * A test greps src/ for PIL/cv2/imread imports, so CLAUDE.md §1's rasterio-only rule is
      enforced by CI rather than by convention.

  TEST-SUITE PLUMBING: tests/synthetic.py holds the SYNTHETIC raster factory and `tests` was
  added to pytest pythonpath, so shared helpers import cleanly without relative-import hacks.

S4 — TAXONOMY LAYER COMPLETE. 49 tests pass. THREE DECISIONS I TOOK WITHOUT SIGN-OFF
  (asked twice, proceeded rather than block a third time — overturn any of these freely):

  D1. ignore_index 255 -> 999. This was a live silent-failure BUG, not a preference. The
      reference maps use 999 for unclassified; the config said 255, a placeholder set at S1
      before any data existed. A loader ignoring 255 would treat 999 as a class index and
      either crash or corrupt the loss. GeoTIFF nodata is declared 0 but 0 never occurs.
      Applied to configs/taxonomy.yaml and the Pydantic schema.

  D2. Head width stays 44. A stratified scan of 17,221 maps across all 54 tiles (seed 1337)
      found 43 CORINE codes + 999. The single absent class is 335 Glaciers and perpetual snow
      — plausible, since glacier patches likely sit in reBEN's snow-filtered set. I kept all
      44 official CORINE L3 classes defined with contiguous indices 0..43, because CLAUDE.md §1
      freezes the 44-class target and the S4 spec requires "all 44 present, contiguous".
      Expect 335 to be a dead output: report it, do not drop it.

  D3. L3->19 is a PARTIAL function, with an explicit no-equivalent bucket. 11 of the 44
      classes have NO 19-class counterpart: 122,123,124,131,132,133,141,142 (artificial
      surfaces beyond urban fabric and industrial units), 332 bare rocks, 334 burnt areas,
      335 glaciers. Those pixels aggregate to NO_EQUIVALENT rather than being silently folded
      into a neighbouring class, and querying such a class at level c19 RAISES TaxonomyError
      rather than returning an empty mask. S3 showed questions are asked exclusively in the
      19-class vocabulary, so these are never legitimately queried at 19 — but the bucket must
      exist for the aggregation to be honest about what it dropped.

  L3->19 MAPPING WAS DERIVED, NOT ASSUMED: co-occurrence between each reference map's L3 codes
  and that patch's official reBEN 19-class multi-label. 32 of 44 resolved at confidence 1.000
  (provenance: derived); 1 ambiguous fell back to documented convention (423 Intertidal flats
  -> Coastal wetlands); 11 have no equivalent. Self-check: the derived mapping covers EXACTLY
  19 distinct classes, no more, no fewer.

  SYNONYMS DERIVED FROM REAL QUESTION TEXT, not invented. Observed forms (measured, with
  occurrence counts) are kept structurally separate from unobserved demo-path additions, so
  measured benchmark vocabulary is never confused with convenience. Six initially-unresolved
  forms were all traced to a parser artifact (splitting MCQ options on "and" fragments the four
  19-class names containing "and"/"or") — zero genuinely unresolved forms remain.

  A TEST BUG WAS FOUND AND FIXED IN MY OWN TEST, not the implementation: the
  aggregation-before-geometry test's precondition used np.isin([111,112]), which already merges
  both classes and so cannot demonstrate over-counting. The real naive failure is labelling each
  L3 class separately and summing. Corrected; the test now genuinely proves the guarantee.

S9 — Q1 RULE PARSER + M10 FALLBACK. COMPLETE. 548 tests pass (up from 433), ruff + mypy clean.
  See reports/evaluation/S9_parser.md, reports/experiments/s9_parser.json,
  DECISIONS.md D-S9-1..4. Built: src/satquery/routing/{parser,m10_classifier}.py.

  *** HELD-OUT VALIDATION: coverage 99.60%  precision 98.44%  end-to-end 98.04% ***
      Combined with M10: 98.44%. Residue 18/4,500 = 0.40%.
      HALT CHECK (stage prompt): coverage 99.60% vs 50% floor -> PASS. The rules are the
      primary path and M10 is a genuine fallback, which is what the architecture intends.

  METHODOLOGY, disclosed (D-S9-4): the rules were written by inspecting parse errors, and early
  iterations inspected VALIDATION errors — making those items development data. Added
  --holdout-skip to sample a disjoint slice development never saw. Dev slice scored
  99.47/98.48/97.96 vs held-out 99.60/98.44/98.04, so the rules generalise. Every number
  reported is the held-out one. The held-out residue was deliberately NOT fixed.

  FIVE DEFECTS FOUND AND FIXED, all measured on real questions:
    * `sea` matched INSIDE the word "season" (14 short forms exposed; `urban` in "suburban",
      `town` in "downtown") -> mcq|season precision was 0.00%. Whole-word matching now.
    * A CLASS NAME was being read as an intent cue: "Land principally occupied by agriculture,
      with significant areas of natural vegetation" contains "occupied" AND "areas", firing two
      AREA cues by itself -> 151 presence questions misrouted. Cues now read class-masked text.
    * MCQ stems ending in ":" not "?" left the option list inside the stem -> 68 misroutes.
    * `m^2` was NEVER MATCHED — 109 of 333 sampled m2 spellings. THE MOST SERIOUS IN KIND: the
      others misroute a question, this one DROPS THE STATED VALUE while still routing to AREA,
      i.e. a confident answer to the wrong question rather than an honest abstention.
    * Caption stems say "including the region, time of year" -> 71 captions hit METADATA_MCQ.
  Each has an assertion in tests/unit/test_query_parser.py that would have caught it.

  A5 CLOSED (D-S9-1): the real intent vocabulary is 9, not the "8-way" CLAUDE.md §1 states.
  15 tasks -> 9 intents; the enum carries a 10th, CHANGE, which has ZERO rows in this benchmark.
  Flagged rather than absorbed: CLAUDE.md §1 and the S9 stage prompt already disagreed with each
  other, and A5 pre-authorised replacing the provisional enum with the measured one.

  M10 (D-S9-2): fitted on ALL 9,000 training questions, not on the rules' residue. Measured —
  the training residue holds 56 items across only 2 intents, so a residue-fitted M10 is
  STRUCTURALLY UNABLE to emit 7 of the 9 intents. Persisted with its training-split hash.
  ITS ACCURACY IS NOT QUOTABLE: the held-out residue is 18 items, only 4 of them unseen text.

S7-ADDENDUM — RELATIVE-POSITION DIRECTION CONVENTION. FITTED. 433 tests pass (up from 395),
  ruff clean, mypy --strict clean. oracle.py previously had NO unit tests at all — which is
  exactly how both of this task's defects shipped; tests/unit/test_oracle_direction.py adds them.
  See reports/evaluation/GATE1_oracle.md §7, reports/experiments/direction_convention.json,
  scripts/fit_direction_convention.py, DECISIONS.md D-S7A-1.

  Ordered by the reviewer after the GATE 1 PASS: S7 had fitted connectivity, MMU, opening and
  dilation but left the direction rule uncalibrated, so Gate 1's own number rested on one
  uncalibrated component. Closed while isolated, before S9/S14 could confound it.

  *** RESULT: mcq|relative pos 65.33% -> 92.67% (+27.34). MACRO 87.11% -> 90.15%. ***
  Attribution is CLEAN: at matched n=300 exactly ONE of nine tasks moved; the other eight are
  bit-identical, and the blind baseline is unchanged at 49.07%.

  MEASURED — decisive:
    * TEMPLATE ORIENTATION was the dominant error, not geometry. 25.96% of stems INVERT
      subject and reference ("Using the <A> as the reference, ... position of the <B>";
      "Relative to the <A>, where does the <B> appear"; "spatial direction from <A> to <B>").
      Read as written they score a FORCED 0.00% — the reversed bearing selects the option 180
      degrees from truth, so it cannot be accidentally right. Fixed in the PARSER
      (oracle.subject_is_second), not in M2: which class is the subject is a wording property.
    * THE TEXTBOOK 8-WAY COMPASS IS WRONG. Equal 45-degree sectors score 87.01% vs 93.57% for a
      narrow diagonal band. Corroborated independently: released answers are cardinal 81.60% of
      the time while cardinals are only ~62% of offered options.
    * Improves in 5/5 folds (+21.36 to +33.13). Not a single-region artifact.

  UNDER-DETERMINED — reported as a non-result, exactly as bin_boundary_rule was:
    * The exact band inside ~[10,22] degrees is NOT resolvable. McNemar exact tests over 2,500
      items separate NO candidate from any other (best p=0.068). 16 is shipped because it is the
      one value where TWO INDEPENDENT lines of evidence converge (inside the accuracy plateau
      AND reproduces the observed diagonal-answer rate). It is NOT the accuracy argmax.
    * direction_reference_rule: mask_centroid and largest_component change ZERO of 2,500
      answers. mask_centroid shipped on non-accuracy grounds — same "a class is its mask"
      semantics as compute_area/compute_count, and a union-bbox centre is maximally sensitive
      to one stray pixel, which is wrong once S13 feeds M2 PREDICTED maps.

  RESIDUAL — measured, not guessed. I guessed the `between` family was the remaining defect;
  MEASURING IT PROVED ME WRONG (between = 95.97%, second best). All four families land within
  93.74%-97.10% and each family's error share tracks its item share. Orientation is fully
  resolved; the remainder is evenly-distributed borderline-angle error, which is what an
  under-determined band predicts. No further convention is claimed.

S8 — GATE 1: ORACLE EXPERIMENT. *** PASSED 2026-08-30 *** (verdict given on the numbers below,
  before the S7 addendum; they are preserved unchanged in GATE1_oracle.md §1-§6)
  See reports/evaluation/GATE1_oracle.md and reports/experiments/GATE_REPORT_S8.md

  *** THE GATE 1 NUMBER (as measured at the gate) ***
      MACRO ORACLE (strict, abstentions = wrong) : 87.11%   -> 90.15% after the addendum
      MACRO ORACLE (attempted only)              : 93.89%   -> 96.92% after the addendum
      MACRO best blind / majority baseline       : 49.07%   (unchanged)
      HEADLINE GAP                               : +38.04 points -> +41.07 after the addendum

  Per task (n=300 each, validation split, 95% bootstrap CI over PATCHES):
      binary|presence     100.00%  [100.0,100.0]   blind 82.67%   gap +17.33
      binary|area          74.33%  [ 69.3, 79.3]   blind 61.00%   gap +13.33  (21.3% abstain)
      binary|count         91.00%  [ 86.7, 94.7]   blind 72.33%   gap +18.67
      binary|adjacency     95.67%  [ 93.3, 97.7]   blind 72.33%   gap +23.34
      mcq|presence         90.67%  [ 87.3, 94.0]   blind 46.67%   gap +44.00
      mcq|area             88.67%  [ 85.3, 92.3]   blind 23.33%   gap +62.00  (11.3% abstain)
      mcq|count           100.00%  [100.0,100.0]   blind 21.67%   gap +71.00
      mcq|adjacency        78.33%  [ 73.0, 83.0]   blind 26.33%   gap +52.00  (20.3% abstain)
      mcq|relative pos     65.33%  [ 59.7, 71.0]   blind 24.67%   gap +40.66

  THE 6.78-POINT STRICT-vs-ATTEMPTED GAP IS ENTIRELY PARSER ABSTENTION, NOT GEOMETRY.
  Those are S9's to fix and are the cheapest points in the project.

  *** M8 GATE (O2 caption oracle): BLEU-4 = 15.35 -> BUILD M8 ***
    Lands in the 10-35 band the architecture predicted. A FIRST RUN SCORED 2.60 and would have
    said "drop symbolic captioning" — that was an ARTIFACT: brevity penalty 0.1205, the template
    ran 3x short and omitted the season/country/climate opening S3 VERIFIED the generator
    appends. 15.35 is still a LOWER bound (BP remains 0.4911).

  *** HONESTY FINDING THAT MUST REACH THE JUDGE PACK ***
    binary|presence: the BLIND baseline scores 82.67% — TF-IDF + linear SVM on question text
    alone, NO IMAGE. The class name predicts the answer, because common classes are usually
    present. The oracle still wins (+17.33) and is perfect, but quoting 100% without 82.67%
    beside it overstates what was demonstrated. Same discipline as the adjacency 57.1% finding.
    By contrast MCQ tasks are NOT language-guessable: blind 21-47% vs oracle 65-100%.

  DIAGNOSIS OF EVERY LOW TASK (required by the stage):
    mcq|relative pos 65.33% - CONVENTION error, not geometry. 0% abstention = genuinely wrong.
      Found and fixed a real bug (option matcher compared a single compass letter as a
      SUBSTRING, so computed SE matched "bottom-left" because "S" in "SE"): 55.33% -> 65.33%.
      Residual is an UNFITTED CONVENTION - the generator resolves diagonals differently.
      S7 fitted connectivity/MMU/opening/dilation but NEVER the direction rule.
      >>> THIS DIAGNOSIS WAS CORRECT AND HAS SINCE BEEN CLOSED: see S7-ADDENDUM above.
      >>> 65.33% -> 92.67% with no change to any geometry measurement code.
    binary|area 74.33% strict / 94.49% attempted - PARSER error (no threshold / no comparator).
    mcq|adjacency 78.33% strict / 98.33% attempted - PARSER error (option-pair splitter).

  NOT MEASURED: referring expression and referring point need IoU against released boxes rather
  than exact match; the harness does not yet score them. METEOR/CIDEr not computed.

S7 — M2 SYMBOLIC GEOMETRY ENGINE + CONVENTION FITTING. COMPLETE. 43 geometry tests, 395 total.

  CONVENTIONS RECOVERED FROM DATA, NOT GUESSED (training split only, fold-stratified,
  scored PER CLASS per the S6 GATE-2 rule). Full tables:
  reports/experiments/geometry_conventions.md
      connectivity        = 4    -> 100.00% per-class count accuracy, +1.50 pts over 8-conn
      min_mapping_unit_px = 0    -> any MMU > 1 STRICTLY HURTS (2 -> 96.66%, 32 -> 85.93%)
      opening_kernel_px   = 0    -> the generator applies no morphological cleanup
      adjacency_dilation  = 1    -> 97.62%; k=0 collapses to 64.55%, so dilation IS required
  100.00% is the signal the architecture predicted: the generator's exact convention has been
  recovered, which is free accuracy for every downstream stage.

  *** S3 GR-2 CONDITION DISCHARGED — AND THE ANSWER IS A NON-RESULT ***
    bin_boundary_rule is UNDER-DETERMINED, not fitted. All three candidate rules scored
    IDENTICALLY (99.9000% per-class, 99.8000% pooled, n=1000) because exact float coverage
    essentially never lands on a decile boundary, so the case does not arise.
    Set to inclusive_lower_exclusive_upper as the STANDARD CONVENTION, for definiteness only.
    IT IS NOT A MEASUREMENT. No result may be attributed to this choice; if an analysis ever
    appears sensitive to it, that sensitivity is itself a bug.

  *** THE FOLD-STRATIFICATION OBLIGATION WAS FAILED ONCE AND REDONE ***
    A first fitting run drew all 1,000 items from FOLD 0 — it took the first N matches. That
    would have fitted a convention on one region's geography, violating the S6 GATE-2 rule.
    Caught by printing the folds represented. Re-run with a per-fold quota; final tables span
    folds 0-4.

  PERFORMANCE FIX THAT S8 DEPENDS ON: extract_regions was 163.89 ms/call, projecting to ~4.3
  HOURS for S8's oracle sweep. skimage.regionprops over every component plus an O(pixels x
  labels) np.isin were replaced with linear-time primitives (bincount for areas, find_objects
  for bboxes, a LUT for the surviving mask). Now 28.10 ms on a worst-case fragmented random
  map and 4.68 ms on REAL reference maps (which are smooth: mean 0.6 components/map).
  S8 projection: 7.4 min for 5,000 patches. Test suite went 151s -> 2.05s.

  A CONFIG GUARD WAS INVERTED, NOT DELETED: test_m2_fitted_parameters_are_unset asserted the
  parameters were UNSET to stop anyone guessing them. S7 fitted them, so the test now pins the
  MEASURED values — changing one without re-running the fit fails there.

  RE-FIT REQUIRED AT S17: these were fitted on GROUND-TRUTH maps. IMPLEMENTATION_MAP §6.2
  requires a second fit against PREDICTED maps, because the optimal cleanup for a noisy map is
  not the optimal cleanup for a clean one. MMU=0 is very likely to change there.

S6 — GEOGRAPHIC SPLITTING & LEAKAGE DETECTION. 22 leakage tests, 347 total. HALTED.

  *** STRATIFIED ALLOCATION RESOLVED MOST OF THE HALT — see GATE_REPORT_S6.md ***
  Block INTEGRITY and block ASSIGNMENT are independent degrees of freedom. The original
  analysis conflated them. Size-balanced packing concentrated a region's classes in a few folds
  as a pure artifact of packing order.
      size-balanced : 17 absent = 14 irreducible + 3 ARTIFACT (132, 141, 421)
      STRATIFIED    : 14 absent = 14 irreducible + 0 artifact   <-- theoretical floor
      floor         : 14 (classes present in <5 tiles; blocks are atomic so NO allocation
                          can place them in all 5 folds)
  Leakage guarantee UNCHANGED: 0 of 419,356 touching pairs split under both. Cost: fold
  balance 0.991 -> 0.954. FINAL SPLIT:
      data/processed/splits/FINAL_s2_tile_stratified_k5_seed1337.json
  The residual 14 are now PROVEN irreducible rather than assumed — measured by counting tiles
  containing each class. Caveat: per-tile presence sampled at 140 maps/tile undercounts very
  rare classes, so 14 is an UPPER bound on irreducibility.

  *** QUEUED VERIFICATION V-S6-1 — low priority, non-blocking, DO NOT let it lapse ***
    The irreducible-14 figure rests on a 140-maps/tile sample, so it is an UPPER bound
    (sampling can only move a class OUT of the irreducible set, never into it — the current
    reporting is therefore conservative in the safe direction). An exhaustive per-tile scan
    would tighten it to the true value. ~20-40 min CPU, no GPU, no network — the natural slot
    is while the S12 GPU rental is idle or warming up.
    DEADLINE: before S24 locks final judge-facing numbers. If unrun by then, S24 must state
    that 14 is a sampled upper bound rather than presenting it as exact.
    See docs/architecture/DECISIONS.md V-S6-1.

  *** GATE 2 / S13 PROPAGATION — MUST BE KNOWN BEFORE S13 STARTS ***
    The transfer factor at S13 MUST be computed PER CLASS over each class's own valid fold set,
    NOT as a single pooled number. The fold-presence set differs per class: 14 classes are
    absent from at least one fold, so a pooled mean averages a different class set per fold and
    is not comparable. Per-class fold coverage must be published beside every number.

  *** ORIGINAL HALT (now largely resolved) — see reports/experiments/GATE_REPORT_S6.md ***
  20 of 44 CORINE L3 classes are absent from at least one fold under geographic blocking.
  STRUCTURAL, not sampling: Portugal has 0 patches in folds 2 and 4, and every Mediterranean
  class missing from exactly those folds is Portugal-concentrated (212, 213, 223, 241, 244,
  323, 522). Three countries occupy a single fold each. 335 Glaciers is absent from every fold,
  matching S4's finding that it is absent from the corpus.
  Geographic blocking prevents leakage PRECISELY BY separating regions, so a regionally
  confined class cannot appear in every fold. The goals are in direct tension.
  RECOMMENDATION: accept, and report per-class IoU only over folds containing the class,
  publishing per-class fold coverage beside every number. Never average over a class a fold
  does not contain. This propagates into GATE 2's transfer factor.

  THE BINDING-vs-LABEL SCRUTINY PAID OFF IMMEDIATELY — carried in from the S5 review:
    Every strategy passes the LABEL check (no block spans folds). Only one passes the BINDING
    check (no physically touching patch pair spans folds):
        country     0 blocks spanning ->    47 touching pairs split (0.0112%)
        grid_1deg   0 blocks spanning -> 8,769 touching pairs split (2.2095%)  <-- edge-of-cell
        s2_tile     0 blocks spanning ->     0 touching pairs split (0.0000%)
    grid_1deg has the BEST fold balance (1.000) and looks perfect by the label check while
    splitting 8,769 physically adjacent pairs. No amount of checking block labels would have
    found it. Adjacency is exact, not inferred: patch ids encode tile/row/col.
    RECOMMENDED STRATEGY: s2_tile.

  TWO JUDGE-FACING NUMBERS (both measured, both on real data):
    1. Physically touching pairs severed by the split, of 419,356 total:
         RANDOM  335,195 (79.93%)      s2_tile  0 (0.00%)
    2. REPEAT ACQUISITIONS — a hazard the architecture did not anticipate. reBEN images the
       same ground location on up to 4 dates. 115,040 distinct (tile,row,col) locations across
       237,871 patches; 69,479 locations carry repeats, involving 192,310 patches = 80.8% OF
       THE TRAINING SPLIT.
         RANDOM  62,195 locations (89.5% of repeats) scatter near-twins across folds
         s2_tile 0 (0.0%)
    Found because a test asserted (tile,row,col) was unique and FAILED. The test's assumption
    was wrong, not the data — investigating rather than "fixing" the assertion surfaced the
    single strongest piece of evidence in the stage.

  RESIDUAL LIMITATION, STATED: within-tile adjacency cannot see across tile boundaries.
  s2_tile's min inter-fold great-circle distance is 0.359 km, below the 1.2 km patch width, so
  cross-tile proximity remains. Sentinel-2 tiles overlap, so this is expected. s2_tile
  eliminates within-tile leakage entirely and reduces but does not eliminate cross-tile
  proximity. The figure is a sampled lower bound.

  ARTIFACTS: data/processed/splits/{country,grid_1deg,s2_tile}_k5_seed1337.json (splits are an
  artifact, not a recomputation), reports/evaluation/split_report.md,
  reports/evaluation/{split_measurements,duplicate_leakage,fold_class_coverage}.json

CLOSED ITEMS
  * GitHub collaborators (5 addresses) — CLOSED 2026-08-30. Handled by the human directly
    through the GitHub web UI. Root constraint for the record: the GitHub API adds
    collaborators by USERNAME, not email; only 1 of 5 addresses resolved to a public username
    (diya240108@gmail.com -> diya-240108), gh CLI was not installed, and no admin-scoped token
    was available. The web UI accepts email addresses; the API does not.

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

    INHERITED HYPOTHESIS — do not rediscover this from scratch:
      A 33.9% logically-impossible-pair rate is high for a dataset as structured as a
      decile-comparator grid. That smells like a SYSTEMATIC bug in the class-attribution /
      pairing logic, not random noise. The 53,261 rows discarded for "ambiguous class
      attribution" (cited as evidence for S14's confidence gate) are very likely the SAME
      underlying issue surfacing a second way.
      DECISION RULE FOR S7: if the contamination rate is still ~30%+ once ground-truth
      coverage is computable, do NOT route around it. Treat it as evidence that the
      class-attribution parser needs the S9-style rule-based rework FIRST — S7's boundary
      confirmation cannot be trusted on top of a parser that mis-attributes a third of pairs.
      If it drops sharply once truth is computed, the pairing heuristic was the culprit and
      the parser is fine.

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
    A5  CLOSED at S9 — measured: 15 tasks -> 9 intents (+CHANGE unused here). D-S9-1.
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
