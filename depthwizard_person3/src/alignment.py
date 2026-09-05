"""CRS-aware SRTM alignment utilities."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.warp import reproject


def _resampling(name: str) -> Resampling:
    try:
        return {"nearest": Resampling.nearest, "bilinear": Resampling.bilinear}[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported resampling method: {name}") from exc


def align_raster_to_target(
    source_path: str | Path,
    target_crs,
    target_transform: Affine,
    target_width: int,
    target_height: int,
    resampling: str = "bilinear",
) -> np.ndarray:
    """Reproject band 1 onto the exact target grid, using NaN for nodata."""
    destination = np.full((target_height, target_width), np.nan, dtype=np.float32)
    try:
        with rasterio.open(source_path) as source:
            if source.count < 1 or source.crs is None:
                raise ValueError("The elevation raster must contain band 1 and a CRS.")
            reproject(
                source=rasterio.band(source, 1),
                destination=destination,
                src_transform=source.transform,
                src_crs=source.crs,
                src_nodata=source.nodata,
                dst_transform=target_transform,
                dst_crs=target_crs,
                dst_nodata=np.nan,
                resampling=_resampling(resampling),
                init_dest_nodata=True,
            )
    except rasterio.errors.RasterioIOError as exc:
        raise ValueError(f"Could not align elevation raster: {exc}") from exc
    if not np.isfinite(destination).any():
        raise ValueError("The elevation raster does not overlap the target GeoTIFF.")
    return destination


def check_alignment(
    first: np.ndarray,
    second: np.ndarray,
    first_crs,
    second_crs,
    first_transform: Affine,
    second_transform: Affine,
) -> None:
    if first.shape != second.shape:
        raise ValueError(f"Aligned raster shape {first.shape} does not match depth {second.shape}.")
    if first_crs != second_crs:
        raise ValueError(f"Aligned CRS {first_crs} does not match target CRS {second_crs}.")
    if not first_transform.almost_equals(second_transform):
        raise ValueError("Aligned raster transform does not match the target pixel grid.")


def estimate_source_scale_pixels(
    source_path: str | Path, target_crs, target_resolution: tuple[float, float]
) -> float:
    """Estimate one source pixel's size in target pixels near its centre."""
    with rasterio.open(source_path) as source:
        if source.crs is None:
            raise ValueError("The elevation raster has no CRS.")
        centre_col = (source.width - 1) / 2.0
        centre_row = (source.height - 1) / 2.0
        x0, y0 = source.transform @ (centre_col, centre_row)
        x1, y1 = source.transform @ (centre_col + 1.0, centre_row)
        x2, y2 = source.transform @ (centre_col, centre_row + 1.0)
        transformer = Transformer.from_crs(source.crs, target_crs, always_xy=True)
        tx0, ty0 = transformer.transform(x0, y0)
        tx1, ty1 = transformer.transform(x1, y1)
        tx2, ty2 = transformer.transform(x2, y2)
    x_size = float(np.hypot(tx1 - tx0, ty1 - ty0)) / max(target_resolution[0], 1e-12)
    y_size = float(np.hypot(tx2 - tx0, ty2 - ty0)) / max(target_resolution[1], 1e-12)
    estimate = (x_size + y_size) / 2.0
    if not np.isfinite(estimate) or estimate <= 0:
        raise ValueError("Could not estimate the elevation raster's scale on the target grid.")
    return estimate
