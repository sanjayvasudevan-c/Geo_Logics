"""Band definitions and the frozen channel order.

CLAUDE.md §1 freezes M1's input at **12 channels**: Sentinel-1 (VV, VH) followed by Sentinel-2
(B02, B03, B04, B05, B06, B07, B08, B8A, B11, B12). That order is a contract — a model trained
with one order and served with another produces confident nonsense with no error anywhere — so
it lives here as a single constant that both training and inference import, and a test asserts
it explicitly.

Sentinel-2 native resolutions differ. The 10 m bands stay at 10 m; the 20 m bands are
bilinearly resampled to 10 m; the 60 m bands (B01, B09, B10) are discarded before they ever
reach this module, per the reference recipe.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "CHANNEL_ORDER",
    "N_CHANNELS",
    "N_OPTICAL",
    "N_SAR",
    "S1_BANDS",
    "S2_10M",
    "S2_20M",
    "S2_60M_DISCARDED",
    "S2_BANDS",
    "band_index",
    "native_resolution_m",
]

#: Sentinel-1 polarisations, in channel order.
S1_BANDS: Final[tuple[str, ...]] = ("VV", "VH")

#: Sentinel-2 bands used, in channel order. CLAUDE.md §1.
S2_BANDS: Final[tuple[str, ...]] = (
    "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12",
)

#: Native 10 m bands — kept at native resolution.
S2_10M: Final[frozenset[str]] = frozenset({"B02", "B03", "B04", "B08"})

#: Native 20 m bands — bilinearly resampled to 10 m.
S2_20M: Final[frozenset[str]] = frozenset({"B05", "B06", "B07", "B8A", "B11", "B12"})

#: Native 60 m bands — DISCARDED. Atmospheric correction and cloud screening bands with
#: limited semantic content; the reference recipe drops them and so do we.
S2_60M_DISCARDED: Final[frozenset[str]] = frozenset({"B01", "B09", "B10"})

#: THE FROZEN CHANNEL ORDER. 2 SAR + 10 optical = 12.
CHANNEL_ORDER: Final[tuple[str, ...]] = S1_BANDS + S2_BANDS

N_SAR: Final[int] = len(S1_BANDS)
N_OPTICAL: Final[int] = len(S2_BANDS)
N_CHANNELS: Final[int] = len(CHANNEL_ORDER)


def band_index(band: str) -> int:
    """Position of a band in :data:`CHANNEL_ORDER`.

    Args:
        band: Band name, e.g. ``"B8A"`` or ``"VV"``.

    Returns:
        Zero-based channel index.

    Raises:
        KeyError: If the band is not part of the frozen order.
    """
    try:
        return CHANNEL_ORDER.index(band)
    except ValueError as exc:
        raise KeyError(f"{band!r} is not one of the {N_CHANNELS} frozen channels") from exc


def native_resolution_m(band: str) -> int:
    """Native ground resolution of a Sentinel-2 band, in metres.

    Args:
        band: Sentinel-2 band name.

    Returns:
        10, 20, or 60.

    Raises:
        KeyError: If the band is not a known Sentinel-2 band.
    """
    if band in S2_10M:
        return 10
    if band in S2_20M:
        return 20
    if band in S2_60M_DISCARDED:
        return 60
    raise KeyError(f"unknown Sentinel-2 band: {band!r}")
