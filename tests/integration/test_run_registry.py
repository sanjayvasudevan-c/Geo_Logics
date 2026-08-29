"""Every run writes a complete, reproducible artifact directory (CLAUDE.md §8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from satquery.config.schema import Config
from satquery.exceptions import ContractViolationError
from satquery.utils.hashing import hash_config
from satquery.utils.run_registry import Run, new_run_id

pytestmark = pytest.mark.integration


class TestRunIds:
    def test_run_id_carries_the_stage(self) -> None:
        assert new_run_id("S1").startswith("S1-")

    def test_run_id_is_filesystem_safe(self) -> None:
        assert not set(new_run_id("S1")) & set('<>:"/\\|?*')


class TestArtifacts:
    def test_writes_all_required_artifacts(self, tmp_path: Path, config: Config) -> None:
        with Run(stage="S1", config=config, seed=1337, root=tmp_path) as run:
            run.record_metrics({"placeholder_metric": 0.0})

        directory = run.directory
        for name in ("config.json", "environment.json", "manifest.json", "metrics.json"):
            assert (directory / name).is_file(), f"{name} missing"

    def test_manifest_records_seed_commit_and_config_hash(
        self, tmp_path: Path, config: Config
    ) -> None:
        with Run(stage="S1", config=config, seed=1337, root=tmp_path) as run:
            pass

        manifest = json.loads((run.directory / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["seed"] == 1337
        assert manifest["stage"] == "S1"
        assert manifest["config_hash"] == hash_config(config)
        assert manifest["failed"] is False
        assert "started_at" in manifest
        assert "finished_at" in manifest

    def test_config_snapshot_round_trips(self, tmp_path: Path, config: Config) -> None:
        with Run(stage="S1", config=config, seed=1, root=tmp_path) as run:
            pass

        snapshot = json.loads((run.directory / "config.json").read_text(encoding="utf-8"))
        assert snapshot["taxonomy"]["num_classes"] == 44
        assert snapshot["project"]["seed"] == config.project.seed

    def test_environment_snapshot_is_complete(self, tmp_path: Path, config: Config) -> None:
        with Run(stage="S1", config=config, seed=1, root=tmp_path) as run:
            pass

        env = json.loads((run.directory / "environment.json").read_text(encoding="utf-8"))
        assert env["python_version"]
        assert "gpu" in env
        assert "packages" in env

    def test_metrics_are_written(self, tmp_path: Path, config: Config) -> None:
        with Run(stage="S1", config=config, seed=1, root=tmp_path) as run:
            run.record_metrics({"oracle_area_accuracy": 0.99, "n": 1082})

        metrics = json.loads((run.directory / "metrics.json").read_text(encoding="utf-8"))
        assert metrics == {"oracle_area_accuracy": 0.99, "n": 1082}


class TestFailureRecording:
    def test_a_failed_run_is_marked_failed(self, tmp_path: Path, config: Config) -> None:
        """CLAUDE.md §5: a failure is reported, never quietly dropped."""
        run = Run(stage="S1", config=config, seed=1, root=tmp_path)
        with pytest.raises(ValueError), run:
            raise ValueError("deliberate failure")

        manifest = json.loads((run.directory / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["failed"] is True
        assert manifest["error_type"] == "ValueError"
        assert "deliberate failure" in manifest["error_message"]


class TestAppendOnly:
    def test_reusing_a_run_id_is_refused(self, tmp_path: Path, config: Config) -> None:
        with Run(stage="S1", config=config, seed=1, run_id="fixed", root=tmp_path):
            pass

        with pytest.raises(ContractViolationError) as info:
            Run(stage="S1", config=config, seed=1, run_id="fixed", root=tmp_path)
        assert info.value.context["run_id"] == "fixed"
