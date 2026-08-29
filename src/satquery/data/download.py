"""Resumable, checksum-verified, idempotent dataset downloads.

STAGE_PROMPTS.md S2 requires download scripts that are "resumable, checksum-verified,
idempotent" and that log "exactly what it fetched and its size".

The three properties, and how each is achieved:

- **Idempotent.** A file already present whose MD5 matches the manifest is skipped entirely.
  Re-running the script after a completed download performs no network I/O.
- **Resumable.** Partial downloads land in ``<name>.part``. On resume the script issues an
  HTTP ``Range`` request for the remaining bytes and appends. A server that ignores ``Range``
  is detected (it answers ``200`` rather than ``206``) and the partial file is restarted rather
  than silently corrupted by appending a second copy of the whole body.
- **Checksum-verified.** The completed file's MD5 is compared against the manifest. A mismatch
  deletes the file and raises — a corrupt archive is never left on disk to be picked up later.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from satquery.exceptions import SatQueryError

__all__ = ["DownloadError", "FileSpec", "download_file", "verify_checksum"]

_CHUNK = 1 << 20  # 1 MiB
_USER_AGENT = "satquery/0.1 (research; contact via repository)"


class DownloadError(SatQueryError):
    """A download failed, or a fetched file failed its integrity check."""


@dataclass(frozen=True)
class FileSpec:
    """One downloadable file and its integrity contract.

    Attributes:
        key: Filename as published by the source.
        url: Direct download URL.
        size_bytes: Expected size. A completed file of a different size is rejected.
        checksum: Expected digest, lowercase hex.
        algorithm: Digest algorithm naming ``checksum``. Zenodo publishes md5; Hugging Face
            publishes sha256 in its ``X-Linked-ETag`` header.
        tier: ``"core"`` (fetched locally) or ``"deferred"`` (too large; cloud instance).
        purpose: Why this project needs the file.
    """

    key: str
    url: str
    size_bytes: int
    checksum: str
    algorithm: str = "md5"
    tier: str = "core"
    purpose: str = ""


def verify_checksum(
    path: Path,
    expected: str,
    *,
    algorithm: str = "md5",
    progress: Callable[[int], None] | None = None,
) -> bool:
    """Stream a file and compare its digest against ``expected``.

    Args:
        path: File to hash.
        expected: Expected lowercase hex digest.
        algorithm: Any algorithm name accepted by :mod:`hashlib`.
        progress: Optional callback receiving cumulative bytes hashed.

    Returns:
        True if the digest matches.
    """
    # Not a security decision: this checks a file against a digest its publisher declared.
    digest = hashlib.new(algorithm)
    seen = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
            seen += len(chunk)
            if progress is not None:
                progress(seen)
    return digest.hexdigest() == expected.lower()


def _open(url: str, *, start: int = 0) -> tuple[object, int]:
    """Open a URL, optionally requesting a byte range. Returns (response, status)."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    if start > 0:
        request.add_header("Range", f"bytes={start}-")
    response = urllib.request.urlopen(request, timeout=120)  # noqa: S310 - https manifest URLs
    return response, response.status


def download_file(
    spec: FileSpec,
    dest_dir: Path,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Fetch one file, resuming and verifying as required.

    Args:
        spec: The file and its integrity contract.
        dest_dir: Directory to download into. Created if absent.
        on_progress: Optional callback ``(bytes_done, total_bytes)``.

    Returns:
        Path to the verified file.

    Raises:
        DownloadError: On a network failure, a size mismatch, or a checksum mismatch. A file
            failing verification is deleted before the error is raised.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / spec.key
    partial = dest_dir / f"{spec.key}.part"

    # Idempotency: an already-correct file means no network I/O at all.
    if (
        final.is_file()
        and final.stat().st_size == spec.size_bytes
        and verify_checksum(final, spec.checksum, algorithm=spec.algorithm)
    ):
        return final

    if final.is_file():
        # Present but wrong. Do not trust it.
        final.unlink()

    start = partial.stat().st_size if partial.is_file() else 0
    if start > spec.size_bytes:
        partial.unlink()
        start = 0

    if start < spec.size_bytes:
        try:
            response, status = _open(spec.url, start=start)
        except (urllib.error.URLError, OSError) as exc:
            raise DownloadError(
                "download failed", key=spec.key, url=spec.url, reason=str(exc)
            ) from exc

        # A server that ignores Range answers 200 with the whole body. Appending it to an
        # existing partial file would silently produce a corrupt archive.
        if start > 0 and status != 206:
            partial.unlink(missing_ok=True)
            start = 0

        mode = "ab" if start > 0 else "wb"
        done = start
        with response, partial.open(mode) as handle:  # type: ignore[attr-defined]
            while chunk := response.read(_CHUNK):  # type: ignore[attr-defined]
                handle.write(chunk)
                done += len(chunk)
                if on_progress is not None:
                    on_progress(done, spec.size_bytes)

    actual = partial.stat().st_size
    if actual != spec.size_bytes:
        raise DownloadError(
            "size mismatch after download",
            key=spec.key,
            expected_bytes=spec.size_bytes,
            actual_bytes=actual,
        )

    if not verify_checksum(partial, spec.checksum, algorithm=spec.algorithm):
        partial.unlink()
        raise DownloadError(
            "checksum mismatch; file deleted",
            key=spec.key,
            algorithm=spec.algorithm,
            expected=spec.checksum,
        )

    partial.replace(final)
    return final
