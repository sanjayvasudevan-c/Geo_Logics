"""Config fingerprinting, so a gate number cannot go stale silently.

**The defect this exists to prevent, measured at S9.** ``configs/synonyms.yaml`` is shared by
the Q1 parser and by the S8 oracle. S9 added two missing surface forms to it for the parser's
benefit — a plural class name and a singular one. That change also improved the oracle's class
resolution, and **Gate 1's macro strict accuracy moved 90.15% -> 92.78% with nobody re-running
the gate.** The number in the report was not wrong when written; it had simply stopped
describing what the code now produces.

A metric report is a claim about a specific configuration. If it does not record which one, the
claim cannot be checked later, and the drift is invisible precisely because nothing failed.

Every gate artifact therefore records the fingerprint of the configs it was measured under, and
a unit test compares that fingerprint against the working tree.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from satquery.utils.paths import project_root

__all__ = ["FINGERPRINTED_CONFIGS", "config_fingerprint"]

#: Configs whose contents can move a measured gate number. Adding a file here is cheap;
#: omitting one that matters reintroduces exactly the silent drift this module exists to catch.
FINGERPRINTED_CONFIGS: tuple[str, ...] = (
    "configs/synonyms.yaml",        # class resolution — moved Gate 1 by +2.63 points at S9
    "configs/m2.yaml",              # the fitted geometry and direction conventions
    "configs/taxonomy/corine_l3.yaml",   # the L3 -> 19 aggregation table
)


def config_fingerprint(root: Path | None = None) -> str:
    """A short stable hash over every config that can move a measured number.

    Args:
        root: Project root. Defaults to the detected repository root.

    Returns:
        The first 16 hex characters of a SHA-256 over the named files, concatenated in the
        fixed order of :data:`FINGERPRINTED_CONFIGS`. Missing files hash as empty rather than
        raising, so a fingerprint is always computable and a deletion still changes it.
    """
    base = root if root is not None else project_root()
    digest = hashlib.sha256()
    for name in FINGERPRINTED_CONFIGS:
        path = base / name
        digest.update(path.read_bytes() if path.is_file() else b"")
    return digest.hexdigest()[:16]
