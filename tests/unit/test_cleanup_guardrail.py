"""The cleanup script refuses temp roots and the harness's own state directory.

CLAUDE.md §9 forbids blanket deletion of a temp root. These tests exist because an ad-hoc
``%TEMP%`` sweep during S2 deleted a running command's output file mid-execution.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SPEC = importlib.util.spec_from_file_location(
    "satquery_cleanup",
    Path(__file__).resolve().parents[2] / "scripts" / "cleanup.py",
)
assert _SPEC is not None and _SPEC.loader is not None
cleanup = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cleanup)


class TestAllowList:
    def test_no_target_is_a_bare_temp_root(self) -> None:
        """The allow-list must never contain a temp root itself."""
        for _label, template in cleanup.CACHE_TARGETS:
            assert template not in ("{TEMP}", "{TEMP}/", "{TMPDIR}"), template

    def test_every_target_is_a_named_cache(self) -> None:
        """Each entry must name a specific subdirectory, not just a root variable."""
        for _label, template in cleanup.CACHE_TARGETS:
            remainder = template.split("}", 1)[-1].strip("/")
            assert remainder, f"{template} resolves to a bare root"

    def test_claude_state_is_declared_protected(self) -> None:
        assert any("claude" in p for p in cleanup.PROTECTED_SUBTREES)


class TestRefusals:
    def test_temp_root_is_refused(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("TEMP", str(tmp_path))
        reason = cleanup._is_protected(tmp_path)
        assert reason is not None
        assert "temp root" in reason

    def test_claude_state_dir_is_refused(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TEMP", str(tmp_path))
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()
        reason = cleanup._is_protected(claude_dir)
        assert reason is not None
        assert "protected" in reason

    def test_path_inside_claude_state_is_refused(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TEMP", str(tmp_path))
        nested = tmp_path / "claude" / "project" / "tasks"
        nested.mkdir(parents=True)
        assert cleanup._is_protected(nested) is not None

    def test_filesystem_root_is_refused(self) -> None:
        root = Path(Path.cwd().anchor)
        reason = cleanup._is_protected(root)
        assert reason is not None

    def test_an_ordinary_cache_dir_is_permitted(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The guard must not be so broad that nothing can ever be cleaned."""
        monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
        (tmp_path / "temp").mkdir()
        cache = tmp_path / "some-cache"
        cache.mkdir()
        assert cleanup._is_protected(cache) is None


class TestDryRunDefault:
    def test_dry_run_deletes_nothing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        marker = tmp_path / ".ruff_cache" / "keep.txt"
        marker.parent.mkdir(parents=True)
        marker.write_text("x", encoding="utf-8")

        monkeypatch.setattr(cleanup, "_project_root", lambda: tmp_path)
        assert cleanup.main([]) == 0

        assert marker.exists(), "dry run must not delete anything"
        assert "nothing deleted" in capsys.readouterr().out

    def test_apply_deletes_an_allow_listed_cache(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cache = tmp_path / ".ruff_cache"
        cache.mkdir()
        (cache / "f.txt").write_text("x", encoding="utf-8")

        monkeypatch.setattr(cleanup, "_project_root", lambda: tmp_path)
        monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
        (tmp_path / "temp").mkdir()

        assert cleanup.main(["--apply"]) == 0
        assert not cache.exists()


class TestRealEnvironment:
    def test_real_claude_temp_dir_would_be_refused(self) -> None:
        """Guards the exact path that was destroyed during S2."""
        temp = os.environ.get("TEMP") or os.environ.get("TMPDIR")
        if not temp:
            pytest.skip("no TEMP set in this environment")
        assert cleanup._is_protected(Path(temp) / "claude") is not None
        assert cleanup._is_protected(Path(temp)) is not None
