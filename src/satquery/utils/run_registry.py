"""Per-run artifact registry.

Stage 1 requirement 7: every run writes ``reports/runs/<run_id>/`` containing a config
snapshot, an environment capture, the seed, the git commit, metrics and logs.

This is the mechanism behind CLAUDE.md §8 — a result that is not accompanied by its config,
seed, commit and environment is not reproducible and therefore not reportable.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from satquery.exceptions import ContractViolationError
from satquery.utils.environment import EnvironmentRecord, capture_environment
from satquery.utils.hashing import hash_config
from satquery.utils.paths import runs_dir

__all__ = ["Run", "new_run_id"]

CONFIG_SNAPSHOT = "config.json"
ENVIRONMENT_SNAPSHOT = "environment.json"
MANIFEST = "manifest.json"
METRICS = "metrics.json"
LOG_FILE = "run.log"


def new_run_id(stage: str) -> str:
    """Mint a run id of the form ``<stage>-<UTC timestamp>``.

    Args:
        stage: Stage name, e.g. ``"S1"``.

    Returns:
        A filesystem-safe run identifier.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stage}-{stamp}"


class Run:
    """A single recorded run.

    Creates ``reports/runs/<run_id>/`` and writes the config snapshot, environment capture and
    manifest on entry; writes metrics on exit. Use as a context manager::

        with Run(stage="S1", config=cfg, seed=1337) as run:
            run.record_metrics({"oracle_count_accuracy": 0.97})

    Args:
        stage: Stage name.
        config: The typed configuration in force. Snapshotted and hashed.
        seed: The global seed in force.
        run_id: Explicit run id. Generated from ``stage`` when omitted.
        root: Runs directory. Defaults to ``reports/runs``.

    Raises:
        ContractViolationError: If the run directory already exists. Runs are append-only;
            silently overwriting a previous run's artifacts would destroy the audit trail.
    """

    def __init__(
        self,
        *,
        stage: str,
        config: Any = None,
        seed: int | None = None,
        run_id: str | None = None,
        root: Path | None = None,
    ) -> None:
        self.stage = stage
        self.run_id = run_id or new_run_id(stage)
        self.seed = seed
        self._config = config
        self._root = (root if root is not None else runs_dir()) / self.run_id

        if self._root.exists():
            raise ContractViolationError(
                "run directory already exists; runs are append-only",
                run_id=self.run_id,
                path=str(self._root),
            )

        self.environment: EnvironmentRecord | None = None

    @property
    def directory(self) -> Path:
        """The run's artifact directory."""
        return self._root

    @property
    def log_path(self) -> Path:
        """Path this run's log file is written to."""
        return self._root / LOG_FILE

    def __enter__(self) -> Run:
        self._root.mkdir(parents=True, exist_ok=False)
        self.environment = capture_environment(seed=self.seed)

        config_payload: Any
        config_hash: str | None
        if self._config is None:
            config_payload, config_hash = None, None
        else:
            config_payload = (
                self._config.model_dump(mode="json")
                if hasattr(self._config, "model_dump")
                else self._config
            )
            config_hash = hash_config(self._config)

        self._write(CONFIG_SNAPSHOT, config_payload)
        self._write(ENVIRONMENT_SNAPSHOT, self.environment.to_dict())
        self._write(
            MANIFEST,
            {
                "run_id": self.run_id,
                "stage": self.stage,
                "seed": self.seed,
                "config_hash": config_hash,
                "git_commit": self.environment.git_commit,
                "git_dirty": self.environment.git_dirty,
                "started_at": self.environment.captured_at,
            },
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        manifest = self._read(MANIFEST)
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        manifest["failed"] = exc_type is not None
        if exc_type is not None:
            manifest["error_type"] = exc_type.__name__
            manifest["error_message"] = str(exc)
        self._write(MANIFEST, manifest)

    def record_metrics(self, metrics: dict[str, Any]) -> Path:
        """Write the run's metrics.

        Args:
            metrics: Metric name to value.

        Returns:
            Path to the written metrics file.
        """
        return self._write(METRICS, metrics)

    def _write(self, name: str, payload: Any) -> Path:
        path = self._root / name
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        return path

    def _read(self, name: str) -> dict[str, Any]:
        raw = (self._root / name).read_text(encoding="utf-8")
        loaded: dict[str, Any] = json.loads(raw)
        return loaded
