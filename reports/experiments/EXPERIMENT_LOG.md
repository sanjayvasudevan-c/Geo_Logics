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
