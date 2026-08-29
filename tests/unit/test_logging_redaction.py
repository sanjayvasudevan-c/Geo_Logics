"""The logger redacts planted fake secrets and external file paths.

Every secret in this file is fabricated for the test. Nothing here is a real credential.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from satquery.utils.logging import configure_logging, get_logger
from satquery.utils.redaction import (
    EXTERNAL_PATH_PLACEHOLDER,
    REDACTED,
    RedactionProcessor,
    redact_value,
)

pytestmark = pytest.mark.unit

# --- SYNTHETIC credentials. Fabricated, non-functional, for redaction testing only. --------
FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
FAKE_GITHUB_TOKEN = "ghp_0123456789abcdefghijklmnopqrstuvwx"
FAKE_HF_TOKEN = "hf_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
FAKE_OPENAI_KEY = "sk-abcdefghijklmnopqrstuvwxyz0123456789"
FAKE_JWT = (
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
    "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
)
FAKE_PEM = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"


def _capture(**fields: object) -> dict[str, object]:
    """Log one record and return it parsed back from JSON."""
    stream = io.StringIO()
    configure_logging(run_id="test-run", stage="S1", stream=stream)
    get_logger("test-component").info("event", **fields)
    payload = stream.getvalue().strip()
    assert payload, "logger produced no output"
    parsed: dict[str, object] = json.loads(payload.splitlines()[-1])
    return parsed


class TestSecretRedaction:
    @pytest.mark.parametrize(
        "key",
        [
            "password", "api_key", "apikey", "secret", "client_secret", "token",
            "access_key", "private_key", "credential", "authorization", "auth",
            "AWS_SECRET_ACCESS_KEY", "HF_TOKEN",
        ],
    )
    def test_secret_bearing_keys_are_redacted(self, key: str) -> None:
        record = _capture(**{key: "super-secret-value"})
        assert record[key] == REDACTED
        assert "super-secret-value" not in json.dumps(record)

    @pytest.mark.parametrize(
        "value",
        [FAKE_AWS_KEY, FAKE_GITHUB_TOKEN, FAKE_HF_TOKEN, FAKE_OPENAI_KEY, FAKE_JWT, FAKE_PEM],
    )
    def test_secret_shaped_values_are_redacted_under_innocuous_keys(self, value: str) -> None:
        """The planted secret must not survive even when the key looks harmless."""
        record = _capture(note=value)
        assert record["note"] == REDACTED
        assert value not in json.dumps(record)

    def test_nested_secrets_are_redacted(self) -> None:
        record = _capture(cfg={"outer": {"api_key": "leaked", "safe": "kept"}})
        cfg = record["cfg"]
        assert isinstance(cfg, dict)
        assert cfg["outer"]["api_key"] == REDACTED
        assert cfg["outer"]["safe"] == "kept"
        assert "leaked" not in json.dumps(record)

    def test_secrets_in_lists_are_redacted(self) -> None:
        record = _capture(values=[FAKE_AWS_KEY, "harmless"])
        assert record["values"] == [REDACTED, "harmless"]

    def test_case_insensitive_key_matching(self) -> None:
        record = _capture(API_KEY="x", Password="y")
        assert record["API_KEY"] == REDACTED
        assert record["Password"] == REDACTED


class TestPathRedaction:
    def test_external_absolute_path_is_replaced(self, repo_root: Path) -> None:
        record = _capture(path="/etc/shadow")
        assert record["path"] == EXTERNAL_PATH_PLACEHOLDER
        assert "/etc/shadow" not in json.dumps(record)

    def test_external_windows_path_is_replaced(self) -> None:
        record = _capture(path="C:\\Users\\someone-else\\private\\notes.txt")
        assert "someone-else" not in json.dumps(record)

    def test_project_internal_path_is_relativised(self, repo_root: Path) -> None:
        record = _capture(path=str(repo_root / "configs" / "m1.yaml"))
        assert record["path"] == "configs/m1.yaml"

    def test_path_objects_are_handled(self, repo_root: Path) -> None:
        record = _capture(path=repo_root / "src" / "satquery")
        assert record["path"] == "src/satquery"

    def test_relative_paths_pass_through(self) -> None:
        record = _capture(path="configs/m2.yaml")
        assert record["path"] == "configs/m2.yaml"


class TestRecordStructure:
    def test_record_carries_run_id_stage_and_component(self) -> None:
        record = _capture(detail="x")
        assert record["run_id"] == "test-run"
        assert record["stage"] == "S1"
        assert record["component"] == "test-component"

    def test_record_is_json_with_level_and_timestamp(self) -> None:
        record = _capture()
        assert record["event"] == "event"
        assert record["level"] == "info"
        assert "timestamp" in record


class TestRedactValueDirectly:
    def test_non_string_scalars_pass_through(self, repo_root: Path) -> None:
        assert redact_value("count", 42, repo_root) == 42
        assert redact_value("ratio", 0.5, repo_root) == 0.5
        assert redact_value("flag", True, repo_root) is True
        assert redact_value("nothing", None, repo_root) is None

    def test_processor_is_callable_as_a_structlog_processor(self, repo_root: Path) -> None:
        processor = RedactionProcessor(repo_root)
        out = processor(None, "info", {"token": "abc", "n": 1})
        assert out == {"token": REDACTED, "n": 1}
