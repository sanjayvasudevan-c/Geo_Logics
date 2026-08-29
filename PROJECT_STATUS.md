LAST UPDATED: 2026-08-29 — Stage S0 Architecture Comprehension

Stage numbering: S0–S26 (our own execution breakdown, per STAGE_PROMPTS.md). This is not the
architecture PDF's numbering — the PDF has only an 8-week plan. The two reconcile via
STAGE_PROMPTS.md Appendix B and CLAUDE.md §11. No edit required to CLAUDE.md or the
architecture documents.

COMPLETED:
- Repo wired to https://github.com/sanjayvasudevan-c/Geo_Logics.git (main); scaffolding;
  .gitignore; CLAUDE.md standing rules; EXPERIMENT_LOG.md initialised.
- S0: read both architecture sources in full and produced docs/architecture/IMPLEMENTATION_MAP.md
  covering all 11 requested sections:
    1. Architecture understanding — the 9 pipeline stages; perception/measurement/language
       separation; the benchmark-construction justification for predict-then-calculate.
    2. Component inventory — V1, P1, Q1, R1, scene cache, Assembler, M1–M10, datasets,
       services, evaluation components, security components.
    3. End-to-end data flow — all 10 intents traced with a component firing matrix.
    4. Model & dataset matrix — 16 rows (component / model / dataset / input / output / metric /
       training strategy / purpose), the provisional intent enum, and the pretraining decision table.
    5. Dependency & error-propagation map — DETERMINISTIC/PROBABILISTIC marking, 13 ranked
       failure modes, 6 of them silent.
    6. Implementation plan — 8-week build order mapped to the known S-anchors, with the 5 reasons
       the geometry engine and oracle experiment precede M1 training.
    7. Testing plan — per-component unit/integration/data/model/pipeline/edge-case matrix plus
       cross-cutting data, regression, e2e, API and security suites.
    8. Accuracy improvement plan — built on TARGET(t) = ORACLE(t) × TRANSFER(t); 10 evaluation
       integrity non-negotiables; the 6-config A1 falsification experiment (GATE 3, S16).
    9. Risk register — 7 categories with likelihood, impact, early-warning signal, mitigation.
   10. Assumptions & ambiguities — the architecture's 10 open questions plus 11 items logged at
       the S0 gate under ASSUMPTION — REQUIRES VALIDATION.
   11. Definition of done — 7 checklist groups, opening with §11.0's working definition of
       "mandatory capabilities". No accuracy thresholds invented.

- S0 gate decisions applied (all five, per the human decision of 2026-08-29):
    * "Mandatory capabilities" defined in IMPLEMENTATION_MAP §11.0 from the architecture PDF
      alone as MC-1 (full 9-stage pipeline for every query family in the answer grammar),
      MC-2 (JSON + evidence + execution trace + PDF output), MC-3 (BHARAT-VAL Indian evaluation).
      Logged as an assumption; used in §9.7 and §11.5. Not blocking.
    * S0–S26 numbering adopted as given. No edit made anywhere.
    * M6 input-format mismatch logged as a flagged High/High integration risk (§9.5) and an
      assumption (§10.2 A3), deferred to S17. No bridging strategy chosen.
    * "A1" naming collision resolved: A1 is reserved exclusively for the S16 falsification
      experiment. The stage-9 assembly component is Assembler (src/inference/assembler.py,
      class AnswerAssembler). Applied throughout the document and binding going forward.
    * Query family / task-count enumeration deferred to S3 (benchmark forensics). The
      provisional 10-way intent enum is used in §3, §4.1 and §7.1, marked PROVISIONAL.

IN PROGRESS:
- (none)

NOT STARTED:
- S1 onward. No code written, no dataset downloaded, no model trained, no metric measured.

TESTS PASSED:      0/0   (no tests exist yet)
TESTS FAILED:      none run

KNOWN ISSUES:
- STAGE_PROMPTS.md is NOT present in the repository. Its S-numbers, stage anchors (S3, S8, S9,
  S13, S16, S17, S23) and the provisional Stage 9 intent enum were supplied at the S0 gate and
  are used on that basis; the full S0–S26 list and Appendix B have not been read. It is now a
  cited authority for the execution plan that anyone cloning the repo cannot read.
  Recommend committing it. (IMPLEMENTATION_MAP §10.2 A2)
- docs/architecture/ contains "SatQuery_Architecture (1) (1).pdf" but CLAUDE.md §0 names
  "SatQuery_Architecture.pdf". Content verified as Architecture B and consistent with
  CLAUDE.md §1 frozen facts. Recommend renaming so §0 resolves. (§10.2 A11)
- The review markdown ("SatQuery_Architecture_Review_v2 (2).md") reviews the PREVIOUS
  architecture (Architecture A). The PDF is Architecture B and already incorporates its
  corrections. Both were read in full; the PDF is canonical, the review is the detailed spec
  behind it.

ARCHITECTURE DEVIATIONS: none

EXPERIMENTS RUN: none

BEST CURRENT METRICS: none — no gate has been reached. Per CLAUDE.md §11, no target exists
until the corresponding measurement exists.

OPEN GATES / DECISIONS AWAITING HUMAN:
- None. All five S0 gate items were decided by the human on 2026-08-29 and are applied above.
  S0 is closed and S1 is unblocked.

  Carried forward as ASSUMPTION — REQUIRES VALIDATION (IMPLEMENTATION_MAP §10.2), each with
  an owning stage — none blocking now:
    A1  mandatory capabilities taken from the architecture document; revisit if the SIH26167
        problem statement is ever supplied
    A2  STAGE_PROMPTS.md absent from the repo — recommend committing it
    A3  M6 live-inference input vs SECOND/CDVQA training data — resolve at S17 from direct
        inspection of the downloaded files, not from dataset literature
    A5  real task vocabulary (8-way vs 10-way vs 15 tasks; none enumerated) — resolve at S3
    A6  does area exclude MMU-dropped components — resolve at S8
    A7  is M5 wired into the caption path — resolve at S8
    A8  how M3/M4 map onto CDVQA's closed 19-category answer set — resolve at S17
    A9  exact European-mIoU stop-rule threshold for Indian adaptation — before S23
    A10 Köppen zone class count k — resolve at S3
    A11 PDF filename does not match CLAUDE.md §0

  Deferred to S3 (benchmark forensics), from REV Appendix B:
    - which CLC level the benchmark's questions use (highest-impact unknown)
    - what metadata rides with each annotation (decides whether M5 is a model, lookup, or discard)
    - distractor spacing; licence status of SECOND/CDVQA/VRSBench/reBEN checkpoints; whether the
      reBEN pretrained checkpoints were trained on train+val+test (leakage risk); Bhoonidhi
      open-data policy
  Deferred to S8: connectivity convention (4 vs 8), MMU, binary tolerance bands
  Blocked on the unavailable problem statement: REV Appendix B questions 6 and 7

NEXT STEP:
- Proceed to Stage S1 per STAGE_PROMPTS.md.
- Note the ordering constraint from IMPLEMENTATION_MAP §6.2: the M2 geometry engine and the
  oracle experiment (GATE 1, S8) precede any M1 training. S3 (benchmark forensics) precedes
  both and resolves the largest cluster of open assumptions.
