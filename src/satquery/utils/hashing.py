"""Content hashing for reproducibility.

CLAUDE.md §8 requires every saved model to record a weight hash and a config hash, and the
scene cache is keyed on ``hash(scene_bytes) + model_version``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

__all__ = ["hash_bytes", "hash_config", "hash_file"]

_CHUNK_SIZE = 1 << 20  # 1 MiB


def hash_bytes(payload: bytes, *, algorithm: str = "sha256") -> str:
    """Hash a bytes payload.

    Args:
        payload: Bytes to hash.
        algorithm: Any algorithm name accepted by :mod:`hashlib`.

    Returns:
        Lowercase hex digest.
    """
    digest = hashlib.new(algorithm)
    digest.update(payload)
    return digest.hexdigest()


def hash_file(path: str | Path, *, algorithm: str = "sha256") -> str:
    """Hash a file's contents, streaming so that large model weights do not load into RAM.

    Args:
        path: File to hash.
        algorithm: Any algorithm name accepted by :mod:`hashlib`.

    Returns:
        Lowercase hex digest.

    Raises:
        FileNotFoundError: If ``path`` does not exist or is not a regular file.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"cannot hash: not a file: {file_path}")

    digest = hashlib.new(algorithm)
    with file_path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def hash_config(config: Any, *, algorithm: str = "sha256") -> str:
    """Hash a configuration object canonically.

    The object is serialised with sorted keys so that two configurations differing only in
    key order hash identically. Pydantic models are dumped first.

    Args:
        config: A Pydantic model, mapping, or any JSON-serialisable structure.
        algorithm: Any algorithm name accepted by :mod:`hashlib`.

    Returns:
        Lowercase hex digest.
    """
    payload = config.model_dump(mode="json") if hasattr(config, "model_dump") else config
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hash_bytes(canonical.encode("utf-8"), algorithm=algorithm)
