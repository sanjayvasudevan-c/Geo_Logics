"""V1 — input validation (pipeline stage 1).

Accepts one or two GeoTIFFs plus a text query and emits a typed :class:`InputManifest`, or
raises :class:`~satquery.exceptions.InputValidationError` naming the exact check that failed.

**Never coerce a broken input into a best-effort manifest.** A silently-repaired input is the
start of a confident wrong answer with a clean-looking trace.

**`rasterio` only.** CLAUDE.md §1 forbids PIL, OpenCV and generic ``imread`` for GeoTIFFs: they
silently drop bands beyond the fourth, silently rescale 16-bit to 8-bit, and silently discard
CRS and geotransform. Every one of those failures is invisible until areas come out wrong by a
constant factor — IMPLEMENTATION_MAP §5.3 ranks it the single most damaging silent failure in
the system.
"""

from __future__ import annotations

import math
import re
import unicodedata
from enum import StrEnum
from pathlib import Path
from typing import Any

import rasterio
from pydantic import BaseModel, ConfigDict, Field
from rasterio.errors import RasterioError

from satquery.exceptions import InputValidationError
from satquery.preprocessing.bands import N_OPTICAL, N_SAR

__all__ = [
    "MAX_METADATA_CHARS",
    "InputManifest",
    "Modality",
    "RasterInfo",
    "sanitise_metadata",
    "validate_inputs",
]

#: Metadata strings from an uploaded file reach the query parser (IMPLEMENTATION_MAP §2.3),
#: so they are a prompt-injection surface. Cap and sanitise them at the boundary.
MAX_METADATA_CHARS = 512

#: Tolerance for comparing geotransforms of a co-registered pair, in units of the CRS.
CO_REGISTRATION_TOL = 1e-6


class Modality(StrEnum):
    """Sensor modality inferred from band count."""

    SAR = "S1"
    OPTICAL = "S2"


def sanitise_metadata(value: str, *, limit: int = MAX_METADATA_CHARS) -> str:
    """Strip control characters and cap length on a metadata string.

    GeoTIFF tags are attacker-controlled when a file is uploaded, and they flow into the query
    path. This removes Unicode control/format categories and truncates.

    Args:
        value: Raw metadata string.
        limit: Maximum characters retained.

    Returns:
        The sanitised string.
    """
    cleaned = "".join(c for c in value if unicodedata.category(c) not in {"Cc", "Cf", "Co", "Cs"})
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


class RasterInfo(BaseModel):
    """Validated facts about a single raster."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    band_count: int = Field(ge=1)
    dtype: str
    crs: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    gsd_x: float = Field(gt=0)
    gsd_y: float = Field(gt=0)
    transform: tuple[float, float, float, float, float, float]
    nodata: float | None
    modality: Modality
    all_nodata: bool
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def shape(self) -> tuple[int, int]:
        """``(height, width)`` in pixels."""
        return (self.height, self.width)


class InputManifest(BaseModel):
    """The typed output of V1. Either this exists and is trustworthy, or an error was raised."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rasters: tuple[RasterInfo, ...]
    query: str
    is_pair: bool
    co_registered: bool | None = Field(
        default=None,
        description="None when a single raster was supplied; otherwise the checked result.",
    )

    @property
    def modalities(self) -> tuple[Modality, ...]:
        """Modality of each supplied raster, in order."""
        return tuple(r.modality for r in self.rasters)


def _infer_modality(band_count: int, path: Path) -> Modality:
    if band_count == N_SAR:
        return Modality.SAR
    if band_count in (N_OPTICAL, N_OPTICAL + 2, 13):
        return Modality.OPTICAL
    raise InputValidationError(
        "cannot infer sensor modality from band count",
        path=str(path.name), band_count=band_count,
        expected=f"{N_SAR} (S1) or {N_OPTICAL}/12/13 (S2)",
        check="modality_inference",
    )


def _inspect(path: Path) -> RasterInfo:
    """Open one raster with rasterio and extract validated facts."""
    if not path.is_file():
        raise InputValidationError(
            "input file not found", path=str(path), check="file_exists"
        )
    try:
        with rasterio.open(path) as ds:
            if ds.crs is None:
                raise InputValidationError(
                    "raster has no CRS", path=path.name, check="crs_present",
                    hint="a GeoTIFF loaded through PIL/OpenCV loses its CRS — use rasterio",
                )
            if ds.transform is None or not ds.transform.is_rectilinear:
                raise InputValidationError(
                    "raster has no usable geotransform", path=path.name,
                    check="geotransform_present",
                )
            gsd_x, gsd_y = abs(ds.transform.a), abs(ds.transform.e)
            if gsd_x <= 0 or gsd_y <= 0:
                raise InputValidationError(
                    "non-positive pixel size", path=path.name,
                    gsd_x=gsd_x, gsd_y=gsd_y, check="gsd_positive",
                )
            modality = _infer_modality(ds.count, path)
            first = ds.read(1, masked=True)
            all_nodata = bool(first.mask.all()) if first.mask is not False else False
            meta = {
                sanitise_metadata(str(k)): sanitise_metadata(str(v))
                for k, v in (ds.tags() or {}).items()
            }
            return RasterInfo(
                path=path.name, band_count=ds.count, dtype=str(ds.dtypes[0]),
                crs=str(ds.crs), width=ds.width, height=ds.height,
                gsd_x=gsd_x, gsd_y=gsd_y,
                transform=tuple(ds.transform)[:6],
                nodata=ds.nodata, modality=modality, all_nodata=all_nodata, metadata=meta,
            )
    except RasterioError as exc:
        raise InputValidationError(
            "raster could not be opened by rasterio", path=path.name,
            reason=str(exc), check="rasterio_open",
        ) from exc


def _check_co_registration(a: RasterInfo, b: RasterInfo) -> bool:
    """Verify two rasters describe the same ground footprint at the same grid."""
    if a.shape != b.shape:
        raise InputValidationError(
            "paired rasters have different shapes", check="pair_shape",
            first=a.shape, second=b.shape,
        )
    if a.crs != b.crs:
        raise InputValidationError(
            "paired rasters have different CRS", check="pair_crs",
            first=a.crs, second=b.crs,
        )
    drift = [abs(x - y) for x, y in zip(a.transform, b.transform, strict=True)]
    if max(drift) > CO_REGISTRATION_TOL:
        raise InputValidationError(
            "paired rasters are not co-registered", check="pair_co_registration",
            max_transform_drift=max(drift), tolerance=CO_REGISTRATION_TOL,
        )
    return True


def validate_inputs(
    paths: list[Path] | tuple[Path, ...],
    query: str,
    *,
    expect_shape: tuple[int, int] | None = None,
) -> InputManifest:
    """Validate one or two GeoTIFFs and a text query.

    Args:
        paths: One or two raster paths.
        query: The natural-language question.
        expect_shape: Optional ``(height, width)`` every raster must match.

    Returns:
        A validated :class:`InputManifest`.

    Raises:
        InputValidationError: On any failed check. The error's ``check`` context field names
            the exact check that failed.
    """
    supplied = [Path(p) for p in paths]
    if not 1 <= len(supplied) <= 2:
        raise InputValidationError(
            "expected 1 or 2 rasters", count=len(supplied), check="input_count"
        )

    cleaned_query = sanitise_metadata(query, limit=4096)
    if not cleaned_query:
        raise InputValidationError("query is empty after sanitisation", check="query_non_empty")

    rasters = tuple(_inspect(p) for p in supplied)

    if expect_shape is not None:
        for r in rasters:
            if r.shape != expect_shape:
                raise InputValidationError(
                    "raster shape does not match the expected patch geometry",
                    path=r.path, shape=r.shape, expected=expect_shape, check="expected_shape",
                )

    co_registered: bool | None = None
    if len(rasters) == 2:
        co_registered = _check_co_registration(rasters[0], rasters[1])

    return InputManifest(
        rasters=rasters, query=cleaned_query,
        is_pair=len(rasters) == 2, co_registered=co_registered,
    )


def manifest_to_dict(manifest: InputManifest) -> dict[str, Any]:
    """Render a manifest for the execution trace."""
    payload: dict[str, Any] = manifest.model_dump(mode="json")
    payload["nan_free"] = all(
        not (r.nodata is not None and math.isnan(r.nodata)) for r in manifest.rasters
    )
    return payload
