"""Validated raster and depth loading for the calibration stage."""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from affine import Affine
from PIL import Image
from pyproj import CRS, Transformer
from rasterio.coords import BoundingBox
from rasterio.transform import array_bounds


@dataclass(frozen=True)
class RasterMetadata:
    path: Path
    crs: object
    transform: Affine
    width: int
    height: int
    bounds: BoundingBox
    resolution: tuple[float, float]
    nodata: float | None
    dtype: str

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width


def read_geotiff_metadata(path: str | Path) -> RasterMetadata:
    raster_path = Path(path)
    if not raster_path.is_file():
        raise FileNotFoundError(f"Target GeoTIFF was not found: {raster_path}")
    try:
        with rasterio.open(raster_path) as dataset:
            if dataset.count < 1:
                raise ValueError("Target GeoTIFF has no raster bands.")
            if dataset.crs is None or dataset.transform.is_identity:
                raise ValueError("Absolute elevation requires a genuinely georeferenced GeoTIFF.")
            # Reject a syntactically present but geographically impossible CRS.
            # This catches, for example, negative northings tagged as a northern
            # UTM zone before they can be fused with an unrelated SRTM tile.
            # Rasterio's CRS object serializes through WKT; feeding that object
            # straight to PyProj can discard the EPSG area-of-use record. Prefer
            # the authority code when one is recoverable, then fall back to WKT.
            epsg = dataset.crs.to_epsg()
            crs = CRS.from_epsg(epsg) if epsg is not None else CRS.from_user_input(dataset.crs)
            centre_x, centre_y = dataset.transform @ (dataset.width / 2, dataset.height / 2)
            longitude, latitude = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(
                centre_x, centre_y
            )
            if not (math.isfinite(longitude) and math.isfinite(latitude)):
                raise ValueError("The target GeoTIFF centre cannot be transformed to a finite location.")
            area = crs.area_of_use
            if area is not None:
                tolerance = 0.5
                inside_latitude = area.south - tolerance <= latitude <= area.north + tolerance
                inside_longitude = (
                    area.west - tolerance <= longitude <= area.east + tolerance
                    if area.west <= area.east
                    else longitude >= area.west - tolerance or longitude <= area.east + tolerance
                )
                if not (inside_latitude and inside_longitude):
                    raise ValueError(
                        f"The target GeoTIFF declares {dataset.crs}, but its centre transforms to "
                        f"{latitude:.5f}, {longitude:.5f}, outside that CRS's area of use."
                    )
            return RasterMetadata(
                path=raster_path,
                crs=dataset.crs,
                transform=dataset.transform,
                width=dataset.width,
                height=dataset.height,
                bounds=dataset.bounds,
                resolution=(abs(float(dataset.res[0])), abs(float(dataset.res[1]))),
                nodata=dataset.nodata,
                dtype=dataset.dtypes[0],
            )
    except rasterio.errors.RasterioIOError as exc:
        raise ValueError(f"Could not read target GeoTIFF: {exc}") from exc


def derive_target_grid(source: RasterMetadata, shape: tuple[int, int]) -> RasterMetadata:
    """Create a smaller geospatial grid covering the exact source footprint.

    This avoids expanding a bounded monocular prediction back to a multi-GB
    source array. Scaling the affine transform is geospatially meaningful: every
    working pixel becomes larger, while CRS, rotation, and outer bounds remain.
    """
    height, width = (int(shape[0]), int(shape[1]))
    if height < 2 or width < 2:
        raise ValueError("A calibration working grid must be at least 2 x 2 pixels.")
    if (height, width) == source.shape:
        return source
    transform = source.transform @ Affine.scale(source.width / width, source.height / height)
    west, south, east, north = array_bounds(height, width, transform)
    return RasterMetadata(
        path=source.path,
        crs=source.crs,
        transform=transform,
        width=width,
        height=height,
        bounds=BoundingBox(west, south, east, north),
        resolution=(math.hypot(transform.a, transform.d), math.hypot(transform.b, transform.e)),
        nodata=source.nodata,
        dtype=source.dtype,
    )


def load_relative_depth(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    depth_path = Path(path)
    if not depth_path.is_file():
        raise FileNotFoundError(f"Relative-depth array was not found: {depth_path}")
    try:
        depth = np.load(depth_path, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Could not load relative-depth array: {exc}") from exc
    if depth.ndim != 2 or depth.size == 0:
        raise ValueError(f"Relative depth must be a non-empty 2-D array; got {depth.shape}.")
    if not np.issubdtype(depth.dtype, np.number):
        raise ValueError("Relative depth must contain numeric values.")
    depth = np.asarray(depth, dtype=np.float32)
    valid = np.isfinite(depth)
    if not valid.any():
        raise ValueError("Relative depth contains no finite samples.")
    return depth, valid


def load_depth_metadata(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    metadata_path = Path(path)
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Depth metadata was not found: {metadata_path}")
    try:
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read depth metadata: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Depth metadata must be a JSON object.")
    return value


def validate_depth_metadata(metadata: dict[str, Any], actual_shape: tuple[int, int]) -> None:
    if not metadata:
        return
    height = metadata.get("output_height")
    width = metadata.get("output_width")
    if height is None or width is None:
        return
    try:
        declared = int(height), int(width)
    except (TypeError, ValueError) as exc:
        raise ValueError("Depth metadata output dimensions must be integers.") from exc
    if declared != actual_shape:
        raise ValueError(
            f"Depth metadata declares shape {declared}, but the array is {actual_shape}."
        )


def match_depth_to_target(
    depth: np.ndarray, target_shape: tuple[int, int], allow_resampling: bool
) -> tuple[np.ndarray, np.ndarray]:
    if depth.shape == target_shape:
        return depth, np.isfinite(depth)
    if not allow_resampling:
        raise ValueError(
            f"Depth shape {depth.shape} does not match target raster {target_shape}. "
            "Use --allow-depth-resampling only when this mismatch is expected."
        )
    warnings.warn(
        f"Resampling relative depth from {depth.shape} to {target_shape}; verify pixel alignment.",
        RuntimeWarning,
        stacklevel=2,
    )
    target_height, target_width = target_shape
    finite = np.isfinite(depth)
    fill = float(np.nanmedian(depth))
    values = np.where(finite, depth, fill).astype(np.float32)
    resized = np.asarray(
        Image.fromarray(values, mode="F").resize(
            (target_width, target_height), Image.Resampling.BILINEAR
        ),
        dtype=np.float32,
    )
    mask = np.asarray(
        Image.fromarray(finite.astype(np.uint8) * 255, mode="L").resize(
            (target_width, target_height), Image.Resampling.NEAREST
        ),
        dtype=np.uint8,
    ) > 0
    resized[~mask] = np.nan
    return resized, mask


def format_raster_summary(label: str, raster: RasterMetadata) -> str:
    return (
        f"{label}:\n"
        f"  path: {raster.path}\n"
        f"  dimensions: {raster.width} x {raster.height}\n"
        f"  CRS: {raster.crs}\n"
        f"  pixel resolution: {raster.resolution[0]:.6g} x {raster.resolution[1]:.6g}\n"
        f"  bounds: {tuple(raster.bounds)}"
    )


def format_depth_summary(depth: np.ndarray, valid: np.ndarray) -> str:
    values = depth[valid]
    return (
        "Relative depth:\n"
        f"  shape: {depth.shape}\n"
        f"  valid samples: {values.size} / {depth.size}\n"
        f"  range: {float(values.min()):.6g} to {float(values.max()):.6g}"
    )
