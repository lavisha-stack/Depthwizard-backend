"""Read local SRTM/elevation rasters and identify conventional SRTM tiles."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.coords import BoundingBox


@dataclass(frozen=True)
class SrtmGrid:
    path: Path
    crs: object
    transform: Affine
    width: int
    height: int
    bounds: BoundingBox
    nodata: float | None


def read_srtm(path: str | Path) -> tuple[np.ndarray, SrtmGrid]:
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"SRTM/elevation raster was not found: {source_path}")
    try:
        with rasterio.open(source_path) as source:
            if source.count < 1 or source.crs is None:
                raise ValueError("SRTM/elevation input must contain band 1 and a CRS.")
            values = source.read(1, masked=True).filled(np.nan).astype(np.float32)
            grid = SrtmGrid(
                source_path,
                source.crs,
                source.transform,
                source.width,
                source.height,
                source.bounds,
                source.nodata,
            )
    except rasterio.errors.RasterioIOError as exc:
        raise ValueError(f"Could not read SRTM/elevation raster: {exc}") from exc
    if not np.isfinite(values).any():
        raise ValueError("SRTM/elevation raster contains no finite elevations.")
    return values, grid


def format_srtm_summary(values: np.ndarray, grid: SrtmGrid) -> str:
    finite = values[np.isfinite(values)]
    return (
        "SRTM/elevation reference:\n"
        f"  dimensions: {grid.width} x {grid.height}\n"
        f"  CRS: {grid.crs}\n"
        f"  finite elevation range: {float(finite.min()):.3f} to {float(finite.max()):.3f} m"
    )


def srtm_tile_names_for_wgs84_bounds(
    left: float, bottom: float, right: float, top: float
) -> list[str]:
    if not all(np.isfinite((left, bottom, right, top))) or left >= right or bottom >= top:
        raise ValueError("Invalid WGS84 bounds.")
    names: list[str] = []
    for latitude in range(math.floor(bottom), math.ceil(top)):
        for longitude in range(math.floor(left), math.ceil(right)):
            lat = f"N{latitude:02d}" if latitude >= 0 else f"S{abs(latitude):02d}"
            lon = f"E{longitude:03d}" if longitude >= 0 else f"W{abs(longitude):03d}"
            names.append(f"{lat}{lon}.hgt")
    return names
