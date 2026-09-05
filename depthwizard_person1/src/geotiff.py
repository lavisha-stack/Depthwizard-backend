"""GeoTIFF inspection and metadata helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from collections import deque
import math

import numpy as np
import rasterio
from affine import Affine
from PIL import Image
from pyproj import CRS, Transformer
from rasterio.enums import MaskFlags, Resampling
from rasterio.io import DatasetReader


def inspect_georeferencing(dataset: DatasetReader) -> tuple[bool, str | None]:
    """Return True only when both a CRS and a useful affine transform exist.

    CRS describes the coordinate system used to locate the image on Earth.
    The affine transform maps pixel positions to coordinates in that system.
    Rasterio sometimes supplies an identity transform for ordinary TIFFs;
    that placeholder is not treated as genuine georeferencing here.
    """
    transform = dataset.transform
    pixel_x = math.hypot(transform.a, transform.d)
    pixel_y = math.hypot(transform.b, transform.e)
    if dataset.crs is None or transform.is_identity or pixel_x <= 0 or pixel_y <= 0:
        return False, "The TIFF has no usable CRS and affine transform."

    # A CRS tag alone is not proof that the coordinates are valid. In
    # particular, a northern UTM CRS with negative northings can transform to a
    # plausible-looking but impossible location in the southern hemisphere.
    try:
        epsg = dataset.crs.to_epsg()
        crs = CRS.from_epsg(epsg) if epsg is not None else CRS.from_user_input(dataset.crs)
        centre_x, centre_y = transform @ (dataset.width / 2, dataset.height / 2)
        longitude, latitude = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(
            centre_x, centre_y
        )
        if not (math.isfinite(longitude) and math.isfinite(latitude)):
            return False, "The declared CRS cannot transform the image centre to a finite location."
        area = crs.area_of_use
        if area is not None:
            tolerance = 0.5
            inside_latitude = area.south - tolerance <= latitude <= area.north + tolerance
            if area.west <= area.east:
                inside_longitude = area.west - tolerance <= longitude <= area.east + tolerance
            else:
                inside_longitude = longitude >= area.west - tolerance or longitude <= area.east + tolerance
            if not (inside_latitude and inside_longitude):
                return False, (
                    f"The declared CRS places the image centre at {latitude:.5f}, {longitude:.5f}, "
                    "outside that CRS's area of use."
                )
    except Exception as error:
        return False, f"The declared georeferencing could not be validated: {error}"
    return True, None


def has_meaningful_georeferencing(dataset: DatasetReader) -> bool:
    return inspect_georeferencing(dataset)[0]


def read_rgb_bands(dataset: DatasetReader, output_shape: tuple[int, int] | None = None) -> np.ndarray:
    """Read up to the first three bands and return rows x columns x 3.

    Images with more than three bands deliberately use bands 1, 2, and 3.
    A one-band image is repeated three times; a two-band image repeats its
    second band as the third channel. These fallbacks maintain the RGB-shaped
    interface, although such data may not represent true natural-colour RGB.
    """
    if dataset.count < 1:
        raise ValueError("The TIFF contains no raster bands.")
    band_indexes = list(range(1, min(dataset.count, 3) + 1))
    read_options = {}
    if output_shape is not None:
        read_options = {
            "out_shape": (len(band_indexes), *output_shape),
            "resampling": Resampling.bilinear,
        }
    band_first = dataset.read(band_indexes, **read_options)
    channel_last = np.moveaxis(band_first, 0, -1)
    if channel_last.shape[2] == 1:
        channel_last = np.repeat(channel_last, 3, axis=2)
    elif channel_last.shape[2] == 2:
        channel_last = np.concatenate(
            [channel_last, channel_last[:, :, 1:2]], axis=2
        )
    return channel_last


def build_valid_mask(dataset: DatasetReader, output_shape: tuple[int, int] | None = None) -> np.ndarray:
    """Combine raster band masks into one True-for-valid 2D mask."""
    selected = list(range(1, min(dataset.count, 3) + 1))
    shape = output_shape or (dataset.height, dataset.width)
    if all(MaskFlags.all_valid in dataset.mask_flag_enums[index - 1] for index in selected):
        return np.ones(shape, dtype=bool)
    masks = dataset.read_masks(
        selected,
        out_shape=(len(selected), *shape),
        resampling=Resampling.nearest,
    )
    return np.all(masks > 0, axis=0)


def _flood_component(allowed: np.ndarray, seeds: list[tuple[int, int]]) -> np.ndarray:
    """Return the four-connected component reachable from seeds."""
    height, width = allowed.shape
    reached = np.zeros_like(allowed, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for row, col in seeds:
        if 0 <= row < height and 0 <= col < width and allowed[row, col] and not reached[row, col]:
            reached[row, col] = True
            queue.append((row, col))
    while queue:
        row, col = queue.popleft()
        if row and allowed[row - 1, col] and not reached[row - 1, col]:
            reached[row - 1, col] = True; queue.append((row - 1, col))
        if row + 1 < height and allowed[row + 1, col] and not reached[row + 1, col]:
            reached[row + 1, col] = True; queue.append((row + 1, col))
        if col and allowed[row, col - 1] and not reached[row, col - 1]:
            reached[row, col - 1] = True; queue.append((row, col - 1))
        if col + 1 < width and allowed[row, col + 1] and not reached[row, col + 1]:
            reached[row, col + 1] = True; queue.append((row, col + 1))
    return reached


def infer_border_content_mask(rgb: np.ndarray, proxy_size: int = 768) -> np.ndarray | None:
    """Detect undeclared black scan borders while retaining dark scene objects.

    Only near-black pixels connected to an outer edge are background candidates.
    We then retain the central connected image region, which removes bright film
    labels embedded in the black border without masking roads or roof shadows.
    """
    height, width = rgb.shape[:2]
    stride = max(1, math.ceil(max(height, width) / proxy_size))
    proxy = rgb[::stride, ::stride]
    if np.issubdtype(proxy.dtype, np.integer):
        info = np.iinfo(proxy.dtype)
        threshold = float(info.min) + 0.04 * float(info.max - info.min)
    else:
        finite = proxy[np.isfinite(proxy)]
        if not finite.size:
            return None
        low, high = np.percentile(finite, (0.5, 99.5))
        threshold = float(low + 0.04 * max(high - low, 0.0))
    dark = np.all(np.isfinite(proxy), axis=2) & (np.max(proxy, axis=2) <= threshold)
    proxy_height, proxy_width = dark.shape
    boundary_seeds = [(0, col) for col in range(proxy_width)]
    boundary_seeds += [(proxy_height - 1, col) for col in range(proxy_width)]
    boundary_seeds += [(row, 0) for row in range(1, proxy_height - 1)]
    boundary_seeds += [(row, proxy_width - 1) for row in range(1, proxy_height - 1)]
    border_background = _flood_component(dark, boundary_seeds)
    fraction = float(border_background.mean())
    if fraction < 0.002 or fraction > 0.45:
        return None

    candidate = ~border_background
    centre = (proxy_height // 2, proxy_width // 2)
    if not candidate[centre]:
        candidates = np.argwhere(candidate)
        if not candidates.size:
            return None
        distance = np.square(candidates[:, 0] - centre[0]) + np.square(candidates[:, 1] - centre[1])
        centre = tuple(candidates[int(np.argmin(distance))])
    content = _flood_component(candidate, [centre])
    if float(content.mean()) < 0.5:
        return None
    if content.shape != (height, width):
        content = np.asarray(
            Image.fromarray(content.astype(np.uint8) * 255, mode="L").resize(
                (width, height), Image.Resampling.NEAREST
            )
        ) > 0
    return content


def extract_metadata(
    dataset: DatasetReader,
    input_path: Path,
    model_shape: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Extract JSON-friendly raster and geospatial metadata."""
    georeferenced, georeference_warning = inspect_georeferencing(dataset)
    transform = dataset.transform
    bounds = dataset.bounds
    parsed_crs = CRS.from_user_input(dataset.crs) if georeferenced else None
    axis = parsed_crs.axis_info[0] if parsed_crs is not None and parsed_crs.axis_info else None
    nodata = dataset.nodata
    if isinstance(nodata, (float, np.floating)) and not math.isfinite(float(nodata)):
        # JSON has no portable NaN/Infinity value. The raster masks still retain
        # the invalid pixels, while metadata uses null for a non-finite marker.
        nodata = None
    return {
        "input_file": input_path.name,
        "input_path": str(input_path.resolve()),
        "input_type": "georeferenced_geotiff" if georeferenced else "non_georeferenced_tiff",
        "is_georeferenced": georeferenced,
        "width": dataset.width,
        "height": dataset.height,
        "bands": dataset.count,
        "rgb_bands_used": list(range(1, min(dataset.count, 3) + 1)),
        "dtype": dataset.dtypes[0] if dataset.dtypes else None,
        "band_dtypes": list(dataset.dtypes),
        "crs": dataset.crs.to_string() if georeferenced else None,
        "declared_crs": dataset.crs.to_string() if dataset.crs is not None else None,
        "georeference_warning": georeference_warning,
        "transform": (
            [transform.a, transform.b, transform.c, transform.d, transform.e, transform.f]
            if georeferenced
            else None
        ),
        # Hypotenuse form also gives the correct resolution for rotated grids.
        "pixel_size_x": math.hypot(transform.a, transform.d) if georeferenced else None,
        "pixel_size_y": math.hypot(transform.b, transform.e) if georeferenced else None,
        "horizontal_units": axis.unit_name if axis is not None else None,
        "horizontal_unit_to_metre": (
            axis.unit_conversion_factor if parsed_crs is not None and parsed_crs.is_projected and axis is not None
            else None
        ),
        "bounds": (
            {"left": bounds.left, "bottom": bounds.bottom, "right": bounds.right, "top": bounds.top}
            if georeferenced
            else None
        ),
        "nodata": nodata,
        "grid_preserved": model_shape in (None, (dataset.height, dataset.width)),
        "model_width": (model_shape or (dataset.height, dataset.width))[1],
        "model_height": (model_shape or (dataset.height, dataset.width))[0],
        "model_to_original_scale_x": dataset.width / (model_shape or (dataset.height, dataset.width))[1],
        "model_to_original_scale_y": dataset.height / (model_shape or (dataset.height, dataset.width))[0],
    }


def open_tiff(input_path: Path, max_model_size: int | None = None) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Load TIFF pixels, a valid mask, and metadata with Rasterio."""
    try:
        with rasterio.open(input_path) as dataset:
            scale = min(1.0, max_model_size / max(dataset.width, dataset.height)) if max_model_size else 1.0
            model_shape = (
                max(2, round(dataset.height * scale)),
                max(2, round(dataset.width * scale)),
            )
            rgb = read_rgb_bands(dataset, model_shape)
            valid_mask = build_valid_mask(dataset, model_shape)
            inferred_content = infer_border_content_mask(rgb) if dataset.nodata is None else None
            if inferred_content is not None:
                valid_mask &= inferred_content
            metadata = extract_metadata(dataset, input_path, model_shape)
            invalid_count = int(valid_mask.size - np.count_nonzero(valid_mask))
            metadata.update({
                "valid_pixel_count": int(valid_mask.size - invalid_count),
                "invalid_pixel_count": invalid_count,
                "valid_fraction": float(1.0 - invalid_count / valid_mask.size),
                "inferred_border_nodata": inferred_content is not None,
            })
    except rasterio.errors.RasterioIOError as error:
        raise ValueError(f"Rasterio could not read TIFF '{input_path}': {error}") from error
    return rgb, valid_mask, metadata


def transform_from_list(values: list[float]) -> Affine:
    """Reconstruct an Affine transform from metadata.json's six values."""
    if len(values) != 6:
        raise ValueError("An affine transform must contain exactly six values.")
    return Affine(*values)
