"""Redaction filter for structured logs.

Stage 1 requirement 4: the logger must prevent secrets and file paths outside the project
from being logged. Two independent hazards:

1. **Secrets.** Credentials reach the process through ``.env`` (see ``.env.example``) and must
   never appear in a log line, a run artifact, or the execution trace.
2. **External paths.** Absolute paths outside the project root leak the machine's directory
   layout — usernames, home directories, unrelated corpora. Paths *inside* the project are
   relativised so logs stay portable and diffable between machines.

The filter is a structlog processor: it walks the event dict recursively and rewrites values
in place, so it applies to everything logged, not only to fields a caller remembered to mark.
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

__all__ = [
    "EXTERNAL_PATH_PLACEHOLDER",
    "REDACTED",
    "RedactionProcessor",
    "redact_value",
]

REDACTED = "***REDACTED***"
EXTERNAL_PATH_PLACEHOLDER = "<external-path>"

#: Substrings that mark a key as secret-bearing. Matched case-insensitively.
SECRET_KEY_MARKERS: tuple[str, ...] = (
    "secret",
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credential",
    "authorization",
    "auth",
    "session_key",
    "client_secret",
)

#: Value-shaped secrets, caught even when the key looks innocuous.
SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),                      # AWS access key id
    re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}"),            # GitHub token
    re.compile(r"hf_[A-Za-z0-9]{20,}"),                   # Hugging Face token
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),                 # generic sk- style key
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),    # PEM private key block
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
)

#: Absolute paths embedded in free text. Windows and UNC forms permit spaces (real paths on
#: this project contain them) and stop only at characters illegal in a path. The POSIX form
#: must start the string or follow whitespace, so that a relative path such as
#: ``configs/m2.yaml`` is not mistaken for an absolute one.
_EMBEDDED_PATH = re.compile(
    r"[A-Za-z]:[\\/][^\n\r\"'<>|*?]*"
    r"|\\\\[^\n\r\"'<>|*?]*"
    r"|(?:^|(?<=\s))/[^\s\n\r\"'<>|*?]+"
)

#: Windows drive-letter prefix, used to recognise an absolute path cross-platform.
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:[\\/]")


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SECRET_KEY_MARKERS)


def _looks_like_secret_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS)


def _is_absolute_pathlike(raw: str) -> bool:
    """Whether ``raw`` looks absolute on *any* platform.

    ``Path.is_absolute`` is platform-specific: on Windows a POSIX path like ``/etc/shadow``
    reports False because it carries no drive. A leaked POSIX path must still be caught when
    the filter runs on Windows, so the check is done textually.
    """
    return raw.startswith(("/", "\\")) or bool(_DRIVE_PREFIX.match(raw))


def _classify_path(raw: str, project_root: Path) -> str | None:
    """Map one absolute path to its replacement.

    Returns:
        The project-relative path for something beneath ``project_root``,
        :data:`EXTERNAL_PATH_PLACEHOLDER` for anything else, or ``None`` if ``raw`` is not an
        absolute path at all (relative paths are already safe and are left alone).
    """
    if not _is_absolute_pathlike(raw):
        return None

    try:
        resolved = Path(raw).resolve()
    except (OSError, ValueError):
        return EXTERNAL_PATH_PLACEHOLDER

    try:
        relative = resolved.relative_to(project_root)
    except ValueError:
        return EXTERNAL_PATH_PLACEHOLDER
    return relative.as_posix() or "."


def _rewrite_paths(text: str, project_root: Path) -> str:
    """Relativise project-internal absolute paths; replace external ones.

    The whole string is tested as a single path first. That is both the common case (a field
    logged as ``path=...``) and the only way to handle a path containing spaces exactly. Only
    when the string is not itself a path does an embedded scan run over it.
    """
    whole = _classify_path(text.strip(), project_root)
    if whole is not None:
        return whole

    def replace(match: re.Match[str]) -> str:
        return _classify_path(match.group(0), project_root) or match.group(0)

    return _EMBEDDED_PATH.sub(replace, text)


def redact_value(key: str, value: Any, project_root: Path) -> Any:
    """Redact a single key/value pair.

    Args:
        key: The field name the value was logged under.
        value: The value to inspect.
        project_root: Resolved project root. Paths beneath it are relativised; paths outside
            it are replaced with :data:`EXTERNAL_PATH_PLACEHOLDER`.

    Returns:
        The value, redacted or rewritten as required.
    """
    if _is_secret_key(key):
        return REDACTED

    if isinstance(value, str):
        if _looks_like_secret_value(value):
            return REDACTED
        return _rewrite_paths(value, project_root)

    if isinstance(value, Path):
        return _rewrite_paths(str(value), project_root)

    if isinstance(value, dict):
        return {k: redact_value(str(k), v, project_root) for k, v in value.items()}

    if isinstance(value, list | tuple):
        rebuilt = [redact_value(key, item, project_root) for item in value]
        return type(value)(rebuilt) if isinstance(value, tuple) else rebuilt

    return value


class RedactionProcessor:
    """structlog processor applying :func:`redact_value` across the whole event dict.

    Args:
        project_root: Project root. Absolute paths beneath it are relativised; anything else
            is replaced with :data:`EXTERNAL_PATH_PLACEHOLDER`.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root.resolve()

    def __call__(
        self,
        logger: Any,
        method_name: str,
        event_dict: MutableMapping[str, Any],
        /,
    ) -> dict[str, Any]:
        """Rewrite every field of ``event_dict``. Signature is structlog's processor protocol."""
        return {
            key: redact_value(str(key), value, self._project_root)
            for key, value in event_dict.items()
        }
