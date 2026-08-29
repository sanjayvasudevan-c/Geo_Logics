LAST UPDATED: 2026-08-29 — Stage 1 Architecture Comprehension

COMPLETED:
- Stage 0: repo wired to https://github.com/sanjayvasudevan-c/Geo_Logics.git (main), scaffolding,
  .gitignore, CLAUDE.md standing rules, EXPERIMENT_LOG.md initialised.
- Stage 1: read both architecture sources in full and produced docs/architecture/IMPLEMENTATION_MAP.md
  covering all 11 requested sections:
    1. Architecture understanding — 9 stages; perception/measurement/language separation;
       the benchmark-construction justification for predict-then-calculate.
    2. Component inventory — V1, P1, Q1, R1, scene cache, A1, M1–M10, datasets, services,
       evaluation components, security components.
    3. End-to-end data flow — all 9 query families traced with a component firing matrix.
    4. Model & dataset matrix — 16 rows (component / model / dataset / input / output / metric /
       training strategy / purpose) + the pretraining decision table.
    5. Dependency & error-propagation map — DETERMINISTIC/PROBABILISTIC marking, 13 ranked
       failure modes, 6 of them silent.
    6. Implementation plan — 8-week build order with the 5 reasons the geometry engine and
       oracle experiment precede M1 training.
    7. Testing plan — per-component unit/integration/data/model/pipeline/edge-case matrix plus
       cross-cutting data, regression, e2e, API and security suites.
    8. Accuracy improvement plan — built on TARGET(t) = ORACLE(t) × TRANSFER(t); 10 evaluation
       integrity non-negotiables; the 6-config falsification experiment.
    9. Risk register — 7 categories, each with likelihood, impact, early-warning signal, mitigation.
   10. Assumptions & ambiguities — the architecture's 10 open questions plus 12 new ambiguities
       identified in this reading (§10.2), each labelled.
   11. Definition of done — 7 checklist groups, no accuracy thresholds invented.

IN PROGRESS:
- (none)

NOT STARTED:
- Stage 2 onward. No code written, no dataset downloaded, no model trained, no metric measured.

TESTS PASSED:      0/0   (no tests exist yet)
TESTS FAILED:      none run

KNOWN ISSUES:
- docs/architecture/ contains "SatQuery_Architecture (1) (1).pdf" but CLAUDE.md §0 names
  "SatQuery_Architecture.pdf". Content verified as Architecture B and consistent with CLAUDE.md §1
  frozen facts. Recommend renaming the file so §0 resolves. (IMPLEMENTATION_MAP §10.2 A12)
- The review markdown ("SatQuery_Architecture_Review_v2 (2).md") reviews the PREVIOUS architecture
  (Architecture A). The PDF is Architecture B and already incorporates its corrections. Both were
  read; the PDF is treated as canonical, the review as the detailed spec behind it.

ARCHITECTURE DEVIATIONS: none

EXPERIMENTS RUN: none

BEST CURRENT METRICS: none — no gate has been reached. Per CLAUDE.md §11, no target exists
until the corresponding measurement exists.

OPEN GATES / DECISIONS AWAITING HUMAN:
  BLOCKING Stage 2/3 (from IMPLEMENTATION_MAP §10.2):
  1. A1 — The "five mandatory capabilities" are referenced in both documents but NEVER enumerated
     in either. This blocks the Definition of Done (§11.3). Source needed: the SIH26167 problem
     statement.
  2. A2 — CLAUDE.md §11 anchors the four gates at stages S8/S13/S16/S23, but no S1–S23+ stage
     decomposition exists in either architecture document (both use an 8-week plan). The four
     gates map to weeks 2/3/4/6. Need either the full stage list, or a decision to amend
     CLAUDE.md §11 to the week numbering. I have not invented a mapping.
  3. A8 — M6 is specified on SECOND (bi-temporal aerial RGB, 512×512, 0.5–3 m, Chinese cities)
     but the deployment/hidden-set input is a co-registered optical+SAR GeoTIFF pair. The bridge
     between the two formats is unspecified. High likelihood, high impact.
  4. A3 — Naming collision: "A1" denotes both the Answer Assembler and the falsification
     ablation experiment. Proposal: rename the assembler to ASM in code.
  5. A5 — Query family count is inconsistent across sources: M10 does 8-way intent classification,
     9 symbolic operations are specified, BigEarthNet.txt spans 15 tasks. None of the three
     vocabularies is enumerated. Prerequisite for R1's registry and M10's label set.

  DEFERRED to week 1 parquet investigation (architecture's own open questions, REV Appendix B):
  - Which CLC level the benchmark's questions use (highest-impact unknown)
  - What metadata rides with each annotation (decides whether M5 is a model, a lookup, or a discard)
  - Connectivity convention (4 vs 8), MMU, distractor spacing, tolerance bands
  - Licence status of SECOND / CDVQA / VRSBench / reBEN checkpoints
  - Whether the reBEN pretrained checkpoints were trained on train+val+test (leakage risk)
  - Whether Bhoonidhi ≥5 m data is genuinely open for a non-government entity
  - Whether the problem statement permits corpora beyond BigEarthNet.txt (if not, the change
    path is impossible — BigEarthNet.txt is single-timestamp)

  ALSO UNRESOLVED (IMPLEMENTATION_MAP §10.2): A6 (does area exclude MMU-dropped components),
  A7 (is M5 wired into the caption path), A9 (how M3/M4 map onto CDVQA's 19-way closed answer
  set), A10 (exact European-mIoU stop-rule threshold for Indian adaptation), A11 (Köppen class
  count k).

NEXT STEP:
- HALTED pending human decisions on the five blocking items above (CLAUDE.md §3).
- Once unblocked, Stage 2 is the week-1 work: reBEN data pipeline, parquet parsing to produce
  docs/ANSWER_GRAMMAR.md, taxonomy YAML + class-mapping layer, evaluation harness skeleton,
  licence audit. Note that per IMPLEMENTATION_MAP §6.2 the geometry engine and oracle experiment
  (GATE 1) precede any M1 training.
