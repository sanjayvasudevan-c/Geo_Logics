"""Frozen per-band normalisation statistics.

CLAUDE.md §7: any preprocessing that *learns parameters* is fitted on training data only.
Normalisation statistics are exactly that. Per-image or per-batch normalisation leaks across
the split and breaks at single-image inference, so statistics are computed once over the
training split, written to ``configs/norm_stats.yaml`` with the split hash and sample count,
and loaded frozen thereafter.

The file records ``split_hash`` and ``n_samples`` so a leakage test can assert that changing
validation data does not change the statistics.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from satquery.exceptions import ConfigError
from satquery.preprocessing.bands import CHANNEL_ORDER
from satquery.utils.paths import project_root

__all__ = ["NORM_STATS", "BandStats", "NormStats", "load_norm_stats"]

NORM_STATS = "configs/norm_stats.yaml"


@dataclass(frozen=True)
class BandStats:
    """Mean and standard deviation for one band, from the training split."""

    mean: float
    std: float


@dataclass(frozen=True)
class NormStats:
    """Frozen normalisation statistics with the provenance needed to trust them.

    Attributes:
        bands: Per-band statistics, keyed by band name.
        split: Which split the statistics were computed over. Must be ``"train"``.
        split_hash: Hash of the exact sample list used, so the statistics can be tied to it.
        n_samples: Number of patches the statistics were computed over.
        computed_at: ISO timestamp.
        sar_units: Units the SAR statistics are expressed in — ``"db"``, since the dB
            conversion happens before standardisation.
    """

    bands: dict[str, BandStats]
    split: str
    split_hash: str
    n_samples: int
    computed_at: str
    sar_units: str = "db"

    def for_band(self, band: str) -> BandStats:
        """Statistics for one band.

        Raises:
            ConfigError: If the band has no statistics — normalising with a guessed mean/std
                would silently shift the input distribution.
        """
        if band not in self.bands:
            raise ConfigError(
                "no normalisation statistics for band",
                band=band, available=sorted(self.bands),
            )
        return self.bands[band]

    def validate_complete(self) -> None:
        """Assert statistics exist for every frozen channel.

        Raises:
            ConfigError: If any channel is missing, or the split is not ``"train"``.
        """
        missing = [b for b in CHANNEL_ORDER if b not in self.bands]
        if missing:
            raise ConfigError(
                "normalisation statistics are incomplete", missing=missing,
                expected=len(CHANNEL_ORDER),
            )
        if self.split != "train":
            raise ConfigError(
                "normalisation statistics must come from the training split only "
                "(CLAUDE.md §7)",
                split=self.split,
            )


@lru_cache(maxsize=1)
def load_norm_stats(path: Path | None = None) -> NormStats:
    """Load frozen normalisation statistics.

    Args:
        path: Statistics YAML. Defaults to ``configs/norm_stats.yaml``.

    Returns:
        Validated :class:`NormStats`.

    Raises:
        ConfigError: If the file is missing, malformed, incomplete, or was not computed over
            the training split.
    """
    target = path if path is not None else project_root() / NORM_STATS
    if not target.is_file():
        raise ConfigError(
            "normalisation statistics not found; they are computed from the TRAINING SPLIT "
            "ONLY by scripts/data/compute_norm_stats.py",
            path=str(target),
        )
    raw: dict[str, Any] = yaml.safe_load(target.read_text(encoding="utf-8"))
    try:
        stats = NormStats(
            bands={
                k: BandStats(mean=float(v["mean"]), std=float(v["std"]))
                for k, v in raw["bands"].items()
            },
            split=str(raw["split"]),
            split_hash=str(raw["split_hash"]),
            n_samples=int(raw["n_samples"]),
            computed_at=str(raw["computed_at"]),
            sar_units=str(raw.get("sar_units", "db")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(
            "normalisation statistics file is malformed", path=str(target), reason=str(exc)
        ) from exc
    stats.validate_complete()
    return stats
