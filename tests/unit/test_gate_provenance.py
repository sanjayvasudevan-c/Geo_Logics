"""Guard: a recorded gate number must still describe the configuration in the working tree.

**Measured at S9.** ``configs/synonyms.yaml`` is shared by the Q1 parser and the S8 oracle. S9
added two missing surface forms for the parser's benefit; that also improved the oracle's class
resolution, and Gate 1's macro strict accuracy moved **90.15% -> 92.78%** with nobody re-running
the gate and nothing failing. The recorded number was not wrong when written — it had simply
stopped describing what the code produces.

Nothing in the suite could catch that, because the drift lived in a *config* rather than in
code, and the gate artifact did not record which config it was measured under. This file closes
that hole: a metric report is a claim about a specific configuration, and a claim that does not
name its configuration cannot be checked.

The mismatch test is expected to FAIL whenever a fingerprinted config changes after a gate was
measured. **That failure is the finding, not a bug in the test** (CLAUDE.md §5). Resolving it
means re-running the gate and adopting the new number, or reverting the config change — both are
decisions, so neither is done automatically.
"""

from __future__ import annotations

import json

import pytest

from satquery.evaluation.provenance import FINGERPRINTED_CONFIGS, config_fingerprint
from satquery.utils.paths import project_root

pytestmark = pytest.mark.unit

GATE_ARTIFACTS = ("reports/evaluation/gate1_oracle.json",)


class TestFingerprint:
    def test_it_is_stable_across_calls(self) -> None:
        assert config_fingerprint() == config_fingerprint()

    def test_it_is_a_short_hex_digest(self) -> None:
        fp = config_fingerprint()
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_every_fingerprinted_config_exists(self) -> None:
        root = project_root()
        missing = [c for c in FINGERPRINTED_CONFIGS if not (root / c).is_file()]
        assert not missing, f"fingerprinted configs missing: {missing}"

    def test_changing_a_config_changes_the_fingerprint(self, tmp_path) -> None:
        """The guard must actually be able to fire — CLAUDE.md §5's vacuous-test corollary."""
        for name in FINGERPRINTED_CONFIGS:
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text("original", encoding="utf-8")
        before = config_fingerprint(tmp_path)
        (tmp_path / FINGERPRINTED_CONFIGS[0]).write_text("edited", encoding="utf-8")
        assert config_fingerprint(tmp_path) != before

    def test_synonyms_is_fingerprinted(self) -> None:
        """It is the file that actually moved a gate, so it must not drop off the list."""
        assert "configs/synonyms.yaml" in FINGERPRINTED_CONFIGS


class TestRecordedGatesDeclareTheirConfig:
    @pytest.mark.parametrize("artifact", GATE_ARTIFACTS)
    def test_the_artifact_records_a_fingerprint(self, artifact) -> None:
        path = project_root() / artifact
        if not path.is_file():
            pytest.skip(f"{artifact} not present")
        prov = json.loads(path.read_text("utf-8")).get("_provenance")
        assert prov is not None, (
            f"{artifact} records no _provenance block, so there is no way to tell which "
            "configuration its numbers describe"
        )
        assert prov.get("config_fingerprint")

    @pytest.mark.parametrize("artifact", GATE_ARTIFACTS)
    def test_the_recorded_gate_still_matches_the_working_tree(self, artifact) -> None:
        """FAILING THIS IS A FINDING, NOT A BUG IN THE TEST.

        It means a fingerprinted config changed since the gate was measured, so the recorded
        number no longer describes what the code produces. Re-run the gate and adopt the new
        number, or revert the config change. Both are decisions; do not silence this.
        """
        path = project_root() / artifact
        if not path.is_file():
            pytest.skip(f"{artifact} not present")
        prov = json.loads(path.read_text("utf-8")).get("_provenance") or {}
        recorded = prov.get("config_fingerprint")
        if not recorded:
            pytest.skip("no fingerprint recorded; covered by the test above")
        current = config_fingerprint()
        assert recorded == current, (
            f"\n*** GATE OF RECORD IS STALE ***\n"
            f"  {artifact}\n"
            f"  measured under config fingerprint : {recorded}\n"
            f"  working tree fingerprint          : {current}\n"
            f"  fingerprinted: {', '.join(FINGERPRINTED_CONFIGS)}\n"
            f"  A shared config changed after the gate was measured, so the recorded number\n"
            f"  no longer describes what this code produces. Re-run the gate and adopt the\n"
            f"  new number, or revert the config change. Do not edit this test to pass."
        )
