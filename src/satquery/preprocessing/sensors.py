"""P1 — sensor normalisation (pipeline stage 2).

Three things here are load-bearing and easy to get silently wrong:

1. **SAR is log-distributed.** Sentinel-1 GRD carries linear backscatter power. Normalising in
   linear space puts almost all dynamic range in the tail, so power is converted to dB first.
   Power is non-negative by definition, but real products contain exact zeros (and, after
   calibration, occasional negatives). ``log10`` of those is ``-inf``/``nan``, which propagates
   silently through training. :func:`linear_to_db` floors them explicitly and reports how many
   it touched rather than quietly producing NaN.

2. **Normalisation statistics come from the training split only.** Per-image or per-batch
   normalisation leaks and breaks at single-image inference (IMPLEMENTATION_MAP §5.3 failure
   #4). Statistics are loaded frozen from ``configs/norm_stats.yaml``.

3. **A dropped band is not a dark band.** Zeroing a band teaches the model "this surface has
   near-zero reflectance", which is a true physical statement about water and shadow. The
   band-presence mask carries "this band was not measured" as a separate, first-class input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from satquery.exceptions import InputValidationError
from satquery.preprocessing.bands import (
    CHANNEL_ORDER,
    N_CHANNELS,
    N_OPTICAL,
    S1_BANDS,
    S2_20M,
    S2_BANDS,
)

__all__ = [
    "DB_FLOOR_POWER",
    "DbConversion",
    "PreprocessedInput",
    "band_presence_mask",
    "linear_to_db",
    "preprocess",
    "resample_to_10m",
    "spectral_index",
    "stack_channels",
    "zscore",
]

FloatArray = npt.NDArray[np.float32]

#: Power floor applied before ``log10``. Corresponds to -50 dB, far below any real Sentinel-1
#: backscatter, so it clamps invalid pixels without distorting valid ones.
DB_FLOOR_POWER: float = 1e-5


@dataclass(frozen=True)
class DbConversion:
    """Result of a linear-power to dB conversion.

    Attributes:
        values: The dB array.
        floored: How many pixels were at or below zero and had to be floored. Reported rather
            than hidden — a large count means the input is not calibrated linear power.
    """

    values: FloatArray
    floored: int


def linear_to_db(power: npt.NDArray[Any], *, floor: float = DB_FLOOR_POWER) -> DbConversion:
    """Convert Sentinel-1 linear backscatter power to decibels.

    ``dB = 10 * log10(power)``, with non-positive power floored to ``floor`` first.

    Args:
        power: Linear power array.
        floor: Minimum power substituted for non-positive values.

    Returns:
        A :class:`DbConversion` carrying the dB array and the floored-pixel count.

    Raises:
        InputValidationError: If the input already contains NaN or infinity — that is a
            corrupt product, not something to silently repair.
    """
    arr = np.asarray(power, dtype=np.float64)
    if not np.isfinite(arr).all():
        raise InputValidationError(
            "SAR input contains NaN or infinity before dB conversion",
            check="sar_finite_input",
            non_finite=int((~np.isfinite(arr)).sum()),
        )
    invalid = arr <= 0.0
    floored = int(invalid.sum())
    safe = np.where(invalid, floor, arr)
    db = (10.0 * np.log10(safe)).astype(np.float32)
    return DbConversion(values=db, floored=floored)


def resample_to_10m(band: npt.NDArray[Any], target_shape: tuple[int, int]) -> FloatArray:
    """Bilinearly resample a 20 m band to the 10 m grid.

    Args:
        band: Source array.
        target_shape: ``(height, width)`` of the 10 m grid.

    Returns:
        The resampled array as float32.

    Raises:
        InputValidationError: If the target shape is not positive.
    """
    height, width = target_shape
    if height < 1 or width < 1:
        raise InputValidationError(
            "invalid resample target shape", target_shape=target_shape, check="resample_shape"
        )
    src = np.asarray(band, dtype=np.float32)
    if src.shape == (height, width):
        return src

    # Bilinear sampling on the pixel-centre grid, which is what a 20 m -> 10 m upsample means.
    src_h, src_w = src.shape
    row = (np.arange(height, dtype=np.float64) + 0.5) * src_h / height - 0.5
    col = (np.arange(width, dtype=np.float64) + 0.5) * src_w / width - 0.5
    row = np.clip(row, 0, src_h - 1)
    col = np.clip(col, 0, src_w - 1)

    r0 = np.floor(row).astype(int)
    c0 = np.floor(col).astype(int)
    r1 = np.minimum(r0 + 1, src_h - 1)
    c1 = np.minimum(c0 + 1, src_w - 1)
    dr = (row - r0)[:, None]
    dc = (col - c0)[None, :]

    top = src[np.ix_(r0, c0)] * (1 - dc) + src[np.ix_(r0, c1)] * dc
    bottom = src[np.ix_(r1, c0)] * (1 - dc) + src[np.ix_(r1, c1)] * dc
    out: FloatArray = (top * (1 - dr) + bottom * dr).astype(np.float32)
    return out


def zscore(band: npt.NDArray[Any], mean: float, std: float) -> FloatArray:
    """Standardise using frozen training-split statistics.

    Args:
        band: Input array.
        mean: Training-split mean for this band.
        std: Training-split standard deviation for this band.

    Returns:
        The standardised array.

    Raises:
        InputValidationError: If ``std`` is not positive — a zero-variance band means the
            statistics file is wrong, and dividing by it would produce inf.
    """
    if not std > 0:
        raise InputValidationError(
            "normalisation std must be positive", std=std, check="norm_std_positive"
        )
    out: FloatArray = ((np.asarray(band, dtype=np.float32) - mean) / std).astype(np.float32)
    return out


def band_presence_mask(present: dict[str, bool] | None = None) -> npt.NDArray[np.float32]:
    """Length-10 optical band-presence vector, in frozen band order.

    ``1.0`` means the band was genuinely measured; ``0.0`` means it was unavailable or dropped.
    This is a first-class model input, not a diagnostic: without it, a zeroed band is
    indistinguishable from a genuinely dark surface.

    Args:
        present: Mapping of Sentinel-2 band name to availability. Bands omitted are treated as
            present. ``None`` means all present.

    Returns:
        Float32 array of length :data:`~satquery.preprocessing.bands.N_OPTICAL`.

    Raises:
        InputValidationError: If an unknown band name is supplied.
    """
    lookup = dict(present or {})
    unknown = set(lookup) - set(S2_BANDS)
    if unknown:
        raise InputValidationError(
            "unknown Sentinel-2 band in presence mask",
            unknown=sorted(unknown), check="band_presence_names",
        )
    return np.array([1.0 if lookup.get(b, True) else 0.0 for b in S2_BANDS], dtype=np.float32)


def spectral_index(kind: str, bands: dict[str, npt.NDArray[Any]]) -> FloatArray:
    """Compute a normalised-difference spectral index.

    These are **ablation candidates, off by default** (CLAUDE.md §1 / configs/preprocessing.yaml).
    They are redundant given the raw bands when all bands are present, and earn their keep only
    under band dropout, where an index computed from surviving bands preserves a relationship a
    zeroed input cannot.

    Args:
        kind: ``"ndvi"`` (B08, B04), ``"ndwi"`` (B03, B08), or ``"ndbi"`` (B11, B08).
        bands: Mapping of band name to array.

    Returns:
        The index in ``[-1, 1]``, with a zero denominator yielding 0.0 rather than NaN.

    Raises:
        InputValidationError: If the index is unknown or a required band is missing.
    """
    pairs = {"ndvi": ("B08", "B04"), "ndwi": ("B03", "B08"), "ndbi": ("B11", "B08")}
    key = kind.lower()
    if key not in pairs:
        raise InputValidationError(
            "unknown spectral index", kind=kind, valid=sorted(pairs), check="index_kind"
        )
    a_name, b_name = pairs[key]
    missing = [n for n in (a_name, b_name) if n not in bands]
    if missing:
        raise InputValidationError(
            "spectral index requires bands that were not supplied",
            kind=key, missing=missing, check="index_bands",
        )
    a = np.asarray(bands[a_name], dtype=np.float32)
    b = np.asarray(bands[b_name], dtype=np.float32)
    denom = a + b
    out: FloatArray = np.where(denom == 0, 0.0, (a - b) / np.where(denom == 0, 1.0, denom))
    return out.astype(np.float32)


def stack_channels(
    sar: dict[str, npt.NDArray[Any]],
    optical: dict[str, npt.NDArray[Any]],
    target_shape: tuple[int, int],
) -> FloatArray:
    """Assemble the frozen 12-channel tensor.

    Channel order is :data:`~satquery.preprocessing.bands.CHANNEL_ORDER` — VV, VH, then the ten
    Sentinel-2 bands. 20 m bands are resampled to the 10 m grid on the way in. A band that is
    absent from the input dictionaries is filled with zeros; the caller must record that in the
    band-presence mask, because zeros alone do not say "not measured".

    Args:
        sar: VV/VH arrays, already dB-converted and standardised.
        optical: Sentinel-2 arrays, already standardised.
        target_shape: ``(height, width)`` of the 10 m output grid.

    Returns:
        Float32 array of shape ``(12, H, W)``.

    Raises:
        InputValidationError: If a supplied band has the wrong shape for its native resolution.
    """
    height, width = target_shape
    out = np.zeros((N_CHANNELS, height, width), dtype=np.float32)

    for i, name in enumerate(CHANNEL_ORDER):
        source = sar if name in S1_BANDS else optical
        if name not in source:
            continue
        arr = np.asarray(source[name], dtype=np.float32)
        if name in S2_20M:
            arr = resample_to_10m(arr, target_shape)
        elif arr.shape != (height, width):
            raise InputValidationError(
                "band has unexpected shape for a 10 m channel",
                band=name, shape=arr.shape, expected=(height, width),
                check="channel_shape",
            )
        out[i] = arr

    assert out.shape[0] == N_CHANNELS == N_OPTICAL + len(S1_BANDS)
    return out


@dataclass(frozen=True)
class PreprocessedInput:
    """The complete model input: the 12-channel tensor and its band-presence mask.

    These two are returned **together, from one declaration of what was measured**, because
    they are only meaningful as a pair. A tensor whose B11 channel is zeroed and a mask that
    claims B11 was present describe contradictory worlds, and nothing downstream could detect
    the disagreement — the model would simply learn from a lie.

    Building them through separate calls made that drift possible. :func:`preprocess` closes it:
    presence is *derived* from the same information that fills the tensor, so the two cannot
    disagree by construction.

    Attributes:
        tensor: Float32 array of shape ``(12, H, W)`` in :data:`CHANNEL_ORDER`.
        band_presence: Float32 array of length 10. ``1.0`` measured, ``0.0`` not measured.
        sar_floored: Non-positive SAR pixels floored during dB conversion, per polarisation.
            Surfaced so a caller calibrating on real Sentinel-1 notices miscalibrated products.
    """

    tensor: FloatArray
    band_presence: npt.NDArray[np.float32]
    sar_floored: dict[str, int]

    @property
    def dropped_bands(self) -> tuple[str, ...]:
        """Optical bands marked not-measured."""
        return tuple(b for b, p in zip(S2_BANDS, self.band_presence, strict=True) if p == 0.0)


def preprocess(
    sar: dict[str, npt.NDArray[Any]],
    optical: dict[str, npt.NDArray[Any]],
    target_shape: tuple[int, int],
    *,
    dropped: set[str] | frozenset[str] | None = None,
    sar_floored: dict[str, int] | None = None,
) -> PreprocessedInput:
    """Assemble the model input, deriving the presence mask from the same source as the tensor.

    A band counts as measured when it is supplied in ``optical`` **and** not named in
    ``dropped``. Unmeasured bands are zero-filled in the tensor and marked ``0.0`` in the mask,
    in one step, so the two can never disagree.

    Args:
        sar: VV/VH arrays, already dB-converted and standardised.
        optical: Sentinel-2 arrays, already standardised. Omit a band to mark it unmeasured.
        target_shape: ``(height, width)`` of the 10 m output grid.
        dropped: Bands present in ``optical`` but to be treated as unmeasured — the band-dropout
            augmentation path, where the array exists but must not be claimed as measured.
        sar_floored: Floored-pixel counts from :func:`linear_to_db`, carried through for the trace.

    Returns:
        A :class:`PreprocessedInput` whose tensor and mask are guaranteed consistent.
    """
    drop = set(dropped or ())
    usable = {b: a for b, a in optical.items() if b not in drop}
    presence = {b: (b in usable) for b in S2_BANDS}
    return PreprocessedInput(
        tensor=stack_channels(sar, usable, target_shape),
        band_presence=band_presence_mask(presence),
        sar_floored=dict(sar_floored or {}),
    )
