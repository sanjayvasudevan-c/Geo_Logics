"""Content hashing is stable and order-independent."""

from __future__ import annotations

from pathlib import Path

import pytest

from satquery.config.schema import Config
from satquery.utils.hashing import hash_bytes, hash_config, hash_file

pytestmark = pytest.mark.unit


class TestHashFile:
    def test_same_content_same_digest(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a.bin", tmp_path / "b.bin"
        a.write_bytes(b"identical payload")
        b.write_bytes(b"identical payload")
        assert hash_file(a) == hash_file(b)

    def test_different_content_different_digest(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a.bin", tmp_path / "b.bin"
        a.write_bytes(b"payload one")
        b.write_bytes(b"payload two")
        assert hash_file(a) != hash_file(b)

    def test_digest_is_hex_sha256(self, tmp_path: Path) -> None:
        path = tmp_path / "x.bin"
        path.write_bytes(b"x")
        digest = hash_file(path)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            hash_file(tmp_path / "absent.bin")

    def test_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            hash_file(tmp_path)

    def test_large_file_streams(self, tmp_path: Path) -> None:
        path = tmp_path / "big.bin"
        path.write_bytes(b"0" * (3 * 1024 * 1024))
        assert len(hash_file(path)) == 64


class TestHashConfig:
    def test_key_order_does_not_change_the_digest(self) -> None:
        assert hash_config({"a": 1, "b": 2}) == hash_config({"b": 2, "a": 1})

    def test_value_change_changes_the_digest(self) -> None:
        assert hash_config({"seed": 1}) != hash_config({"seed": 2})

    def test_pydantic_models_are_hashable(self, config: Config) -> None:
        digest = hash_config(config)
        assert len(digest) == 64
        assert hash_config(config) == digest

    def test_differing_configs_hash_differently(self, config: Config) -> None:
        other = config.model_copy(update={"project": config.project.model_copy(update={"seed": 1})})
        assert hash_config(config) != hash_config(other)


class TestHashBytes:
    def test_known_empty_digest(self) -> None:
        assert hash_bytes(b"") == (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
