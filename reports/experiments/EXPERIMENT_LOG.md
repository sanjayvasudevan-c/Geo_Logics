# Experiment Log

Per CLAUDE.md §6: minor implementation improvements that do not alter intended
architectural behaviour are logged here rather than routed through the full
"Proposed Architecture Change" process. Architecture-altering changes still
require a `=== PROPOSED ARCHITECTURE CHANGE ===` block and explicit approval.

Format per entry:

```
## <date> — <short title>
Stage:
Change:
Reason:
Effect (measured, not assumed):
```

---

## 2026-08-29 — Python package uses src-layout under `src/satquery/`

Stage: S1

Change: The stage prompt specified `src/` split into `data/`, `preprocessing/`, `taxonomy/`,
`geometry/`, `models/`, `routing/`, `inference/`, `evaluation/`, `api/`, `security/`, `utils/`.
Implemented as `src/satquery/<subpackage>/` rather than `src/<subpackage>/`.

Reason: Three concrete problems with the flat form.
1. `src/data/` would be importable as top-level `data`, colliding with the repo-root `data/`
   dataset directory that the same stage also requires. Two different things named `data` in
   one project is exactly the ambiguity CLAUDE.md §9 ("hidden global state", "duplicated
   logic") exists to prevent.
2. Top-level modules named `models`, `api`, `evaluation` and `utils` are common enough to
   shadow or be shadowed by third-party packages on `sys.path`.
3. There would be no distribution package name, so `pyproject.toml` could not declare a wheel
   and `uv sync` could not install the project in editable form — which the test suite relies
   on for imports.

All eleven named subpackages exist exactly as specified, one level deeper. No behaviour is
altered.

Effect (measured): `uv sync --extra dev` installs `satquery==0.1.0` from the working tree;
171 tests import `satquery.*` successfully. No import collision with the repo-root `data/`.

---

## 2026-08-29 — Added `ConfigError` to the exception hierarchy

Stage: S1

Change: The stage prompt named `SatQueryError` plus `InputValidationError`, `TaxonomyError`,
`GeometryError`, `RoutingError`, `ModelError`, `ContractViolationError`. Added one more:
`ConfigError(SatQueryError)`.

Reason: The stage also requires "invalid config raises a typed error". None of the six named
subclasses fits — `InputValidationError` is reserved for V1's GeoTIFF rejection path
(IMPLEMENTATION_MAP §2.1), and overloading it would make the two failure modes
indistinguishable in the execution trace. Config failure is a distinct, real category.

Effect (measured): 8 config-failure tests assert `ConfigError` with structured context naming
the offending fields. `test_config_error_is_a_satquery_error` confirms it is catchable as the
base type, and `test_hierarchy_is_flat_under_the_base` confirms it shadows no sibling.

---

## 2026-08-29 — Added `scripts/tasks.py` alongside the Makefile

Stage: S1

Change: The stage required `make lint`, `make typecheck`, `make test`. The `Makefile` is
written with those targets, but GNU `make` is not installed on the development machine
(`make`, `mingw32-make`, `gmake`, `nmake` all absent). Added a dependency-free Python task
runner exposing the identical commands.

Reason: CLAUDE.md §5 forbids claiming a test passed that was not executed. The Makefile
targets are therefore **NOT YET VERIFIED** on this machine. Rather than report unverified
targets as working, the same commands are made runnable through a path that can actually be
executed and shown.

Effect (measured): `uv run python scripts/tasks.py check` runs ruff, mypy and pytest in
sequence — all three pass. The `Makefile` remains the canonical target list and is unmodified
in intent; it is expected to work wherever `make` is installed, but that is untested.

---

## 2026-08-30 — Reference-map archive is exhaustive: 549,488 maps, not 480,038

Stage: S2

Change: None to the architecture. A correction to a planning figure.

Reason: Storage was projected from `metadata.parquet`, which lists 480,038 patches (reBEN
after snow/cloud/shadow screening). `Reference_Maps.tar.zst` in fact contains a map for **all
549,488** reBEN patches, including the 69,450 screened out — 14.5% more than projected.

Effect (measured): extraction produced 549,488 maps across 54 tile shards, 533,265,639 B
logical, `complete: true`, 0 patch ids without a parsable tile. Anyone sizing storage from
`metadata.parquet` will under-count by the same 14.5%.

---

## 2026-08-30 — Corrected per-map storage cost: ~4,621 B allocated, not 3,670 B

Stage: S2

Change: None to the architecture. A corrected reference figure.

Reason: The initial 3,670 B/map came from a probe extracting 5,000 maps into a **flat**
directory. The production layout shards by Sentinel-2 tile, which adds per-directory metadata
and MFT growth the flat probe did not capture.

Effect (measured): the final extraction pass wrote 139,488 maps for 644,595,712 B of
free-space delta = **4,621 B/map allocated**, against 970.5 B/map logical — a ~4.76x slack
factor on NTFS 4 KiB clusters. Full store ~2.54 GB on disk. The flat probe under-projected by
~25%. Measure in the target layout, not a flat one.

Also fixed a real bug this exposed: on a **resumed** run the manifest divided that run's
free-space delta by the TOTAL map count, silently under-reporting per-map cost. Fields renamed
to `allocated_bytes_this_run`, `bytes_per_map_allocated_this_run`,
`estimated_total_allocated_bytes`.

---

## 2026-08-30 — Long-running jobs need explicit sleep prevention on this machine

Stage: S2

Change: Added `src/satquery/utils/keepawake.py` and wired it into the extraction script.

Reason: The reference-map extraction was killed twice. Windows System event log identified the
first cause precisely: Modern Standby. The active power scheme sleeps after 600 s on AC and
300 s on battery, and a background job produces no user input, so any run longer than that
window dies. The second kill had a different cause — the task ended when the assistant turn
ended — which is why the fix alone was not sufficient and the run was finally completed as
foreground chunks under the 595 s tool cap.

Effect (measured): A/B evidence. Control (no keep_awake): killed by Modern Standby, log shows
"exiting Modern Standby" 06:50:09. Treatment (keep_awake active): a continuous 616.9 s pass —
past the 600 s AC threshold — completed with zero standby events across the whole 06:50-07:32
window. Same workload and I/O; the only difference was the power request.

A settings change was deliberately NOT made: `SetThreadExecutionState` is process-scoped and
releases on exit, whereas editing the user's power scheme is persistent and easy to leave
behind. Residual uncertainty: `powercfg /requests` needs elevation, so registration was never
observed directly — the evidence is behavioural.
