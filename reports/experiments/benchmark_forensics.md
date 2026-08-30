# Benchmark Forensics — S3 analysis log

Companion to `docs/architecture/ANSWER_GRAMMAR.md`. Code paths, commands, and raw outputs.

**Split discipline:** every measurement below reads `train`+`validation` only. Verified by
`f00_quarantine_audit.py` — **VERDICT: PASS**. See ANSWER_GRAMMAR.md §0.

## Reproducing

```bash
uv run python scripts/forensics/f00_quarantine_audit.py   # run FIRST — proves the seal held
uv run python scripts/forensics/f01_schema.py
uv run python scripts/forensics/f02_templates.py
uv run python scripts/forensics/f03_classes.py
uv run python scripts/forensics/f04_verify_halts.py
uv run python scripts/forensics/f05_numeric.py
uv run python scripts/forensics/f06_boundaries.py
uv run python scripts/forensics/f07_metadata.py
uv run python scripts/forensics/f08_s7_residual.py
```

Each writes JSON to `reports/experiments/forensics/`.

## The quarantine mechanism

All annotation access goes through `satquery.evaluation.forensics.iter_annotations`, which
filters `bench` **inside** the row-group loop before yielding, and raises
`ContractViolationError` if `bench` is requested. Callers cannot forget to filter.
8 unit tests: `tests/unit/test_forensics_quarantine.py`.

The audit checks this three ways — static (no script bypasses the loader), runtime (a full
7,128,971-row pass observes only `train`/`validation`), and column-level (a record of which
columns were ever read for bench rows, project-wide: `input`/`output` never were).

## Script → item map

| Script | S3 items | Rows scanned | Key output |
|---|---|---|---|
| `f00_quarantine_audit.py` | — | 7,128,971 (full pass) | PASS; 0 bench rows observed |
| `f01_schema.py` | 1 | 7,128,971 (full pass) | 13 columns, 0 nulls anywhere |
| `f02_templates.py` | 4, 8, 10 | ~1.47M (12 groups) | Template skeletons + answer vocabularies per task |
| `f03_classes.py` | 2 | ~1.22M (10 groups) | 19-class vocabulary; 0 options outside it |
| `f04_verify_halts.py` | 2, 5 | 1,227,849 (14 groups) | Substring false positives resolved; both units present |
| `f05_numeric.py` | 5, 6 | 1,227,849 (14 groups) | 11 decile bins; 144,000 m² granularity |
| `f06_boundaries.py` | 6, 7, 9, 10 | 1,227,849 (14 groups) | Spacing, near-miss deltas, priors, qualifiers |
| `f07_metadata.py` | 3 | 695,015 (8 groups) | Metadata = label, 100.00% agreement |
| `f08_s7_residual.py` | 5, 7 follow-up | 866,449 (10 groups) | Options 100% ranges; 68.2% share endpoints |

Sampling note: items requiring only distributional shape were computed on a row-group sample
rather than the full 7.1M rows, for runtime. Sample sizes are stated per section in
ANSWER_GRAMMAR.md. Schema and quarantine checks used a full pass.

## Headline measurements

```
Task space              15 type x category combinations
Class vocabulary        19 distinct; 19/19 mcq/presence options inside; 0 outside
Area quantisation       11 distinct values; gaps min=median=mode=144,000 m2 (=10%)
Patch area              1,440,000 m2 = 120 x 120 px x (10 m)^2
Unit relationship       area_m2 = percent x 14,400
MCQ area options        100% ranges (173,684/173,684); 68.2% share an endpoint with the next
MCQ distractor gaps     exact multiples of one decile; additive, not multiplicative
Binary area forms       >=72.3% explicit comparator or range membership
Binary count forms      >=88.4% explicit comparator
Near-miss |stated-true| p25=20, median=40, p75=60 percentage points (near-uniform, not banded)
Metadata columns        100.00% identical to the correct MCQ answer => label, not input
Answer priors           binary 50.0/50.0 except adjacency 57.1 no / 42.9 yes; MCQ ~25% each
Referring qualifiers    {largest, smallest} x 8 phrasings; ~55% have no qualifier
Adjacency synonyms      9 (touch, adjacent, border, next to, contact, meet, neighbour, abut,
                        side by side); no dilation convention inferable
```

## Outcome

Four contradictions of named architectural decisions → `GATE_REPORT_S3.md`.
GR-1 (19-class vocabulary), GR-2 (decile quantisation), GR-3 (M4 metric — §6 change block),
GR-4 (M3 structure — §6 change block).

**S3 is HALTED pending those decisions.**

## Known gaps in this analysis

- **27.7% of binary area and 11.6% of binary count question forms were unmatched** by the
  comparator regex. They may be further comparator phrasings or genuine equality items. This
  makes GR-4's deterministic share a **lower bound**. Cheap to close; recommended next.
- **Near-miss deltas are biased** by taking the lower bound of range-form questions as "stated".
  Settling it needs true per-19-class coverage from reference maps, which needs the S4
  aggregation table. Deferred to S7/S8.
- **Captions were not analysed in depth.** Caption answers do contain `square_metres` (42,036)
  and `thousand_m2` (41,987) patterns, so the caption path may retain the finer 1,000 m²
  convention the VQA path does not. Open question, relevant to M8's gate at S8.
- **Whether the eval harness supplies metadata as an input at inference** cannot be answered
  from the parquet. INCONCLUSIVE; needs the harness specification.
