"""SYNTHETIC GeoTIFF factory for V1 and preprocessing tests.

SYNTHETIC per CLAUDE.md §7: generated data, permitted only for unit, pipeline, stress and
edge-case tests. No real reBEN imagery exists locally — it is the 117.69 GB deferred tier — so
every raster exercised by the S5 test suite is built here from known values.

Because the values are known exactly, these fixtures test correctness rather than plausibility:
a dB conversion is checked against arithmetic, not against "looks about right".
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

__all__ = ["write_synthetic_raster"]

DEFAULT_CRS = "EPSG:32633"
DEFAULT_GSD = 10.0


def write_synthetic_raster(
    path: Path,
    *,
    bands: int = 2,
    height: int = 120,
    width: int = 120,
    dtype: str = "float32",
    crs: str | None = DEFAULT_CRS,
    gsd: float = DEFAULT_GSD,
    origin: tuple[float, float] = (500000.0, 5000000.0),
    fill: float | None = None,
    nodata: float | None = None,
    descriptions: tuple[str, ...] | None = None,
    tags: dict[str, str] | None = None,
) -> Path:
    """Write a SYNTHETIC GeoTIFF with fully controlled properties.

    Args:
        path: Output path.
        bands: Band count. 2 infers SAR, 10 infers optical.
        height: Raster height in pixels.
        width: Raster width in pixels.
        dtype: Numpy dtype name.
        crs: CRS string, or ``None`` to write a raster with no CRS.
        gsd: Pixel size in CRS units.
        origin: Top-left ``(x, y)``.
        fill: Constant fill value. ``None`` yields a deterministic ramp.
        nodata: NoData value to declare.
        descriptions: Per-band names, e.g. ``("VV", "VH")``.
        tags: GeoTIFF metadata tags.

    Returns:
        The written path.
    """
    transform = from_origin(origin[0], origin[1], gsd, gsd)
    if fill is None:
        base = np.arange(height * width, dtype=np.float64).reshape(height, width)
        data = np.stack([base + i for i in range(bands)]).astype(dtype)
    else:
        data = np.full((bands, height, width), fill, dtype=dtype)

    profile = {
        "driver": "GTiff", "height": height, "width": width, "count": bands,
        "dtype": dtype, "transform": transform,
    }
    if crs is not None:
        profile["crs"] = crs
    if nodata is not None:
        profile["nodata"] = nodata

    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(data)
        if descriptions:
            for i, name in enumerate(descriptions[:bands], start=1):
                ds.set_band_description(i, name)
        if tags:
            ds.update_tags(**tags)
    return path
