"""Detect and load supported image inputs without changing their pixel grid."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

from .geotiff import open_tiff


@dataclass
class LoadedImage:
    """Pixels and metadata passed to the preprocessing/output stages."""

    original_rgb: np.ndarray
    valid_mask: np.ndarray
    metadata: dict[str, Any]


def _load_standard_image(input_path: Path, max_model_size: int | None = None) -> LoadedImage:
    """Load a PNG/JPEG as RGB and explicitly mark it non-georeferenced."""
    try:
        with Image.open(input_path) as image:
            original_width, original_height = image.size
            converted = image.convert("RGB")
            if max_model_size and max(converted.size) > max_model_size:
                converted.thumbnail((max_model_size, max_model_size), Image.Resampling.LANCZOS)
            rgb = np.asarray(converted)
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError(f"Pillow could not read image '{input_path}': {error}") from error

    height, width = rgb.shape[:2]
    metadata: dict[str, Any] = {
        "input_file": input_path.name,
        "input_path": str(input_path.resolve()),
        "input_type": "standard_image",
        "is_georeferenced": False,
        "width": original_width,
        "height": original_height,
        "bands": 3,
        "rgb_bands_used": [1, 2, 3],
        "dtype": str(rgb.dtype),
        "band_dtypes": [str(rgb.dtype)] * 3,
        "crs": None,
        "transform": None,
        "pixel_size_x": None,
        "pixel_size_y": None,
        "bounds": None,
        "nodata": None,
        "grid_preserved": (width, height) == (original_width, original_height),
        "model_width": width,
        "model_height": height,
        "model_to_original_scale_x": original_width / width,
        "model_to_original_scale_y": original_height / height,
    }
    return LoadedImage(rgb, np.ones((height, width), dtype=bool), metadata)


def load_image(input_path: Path, max_model_size: int | None = None) -> LoadedImage:
    """Load TIFF through Rasterio and PNG/JPEG through Pillow."""
    if input_path.suffix.lower() in {".tif", ".tiff"}:
        rgb, valid_mask, metadata = open_tiff(input_path, max_model_size=max_model_size)
        return LoadedImage(rgb, valid_mask, metadata)
    return _load_standard_image(input_path, max_model_size=max_model_size)
