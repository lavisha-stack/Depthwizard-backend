"""Load common RGB image formats without changing pixel orientation."""

from pathlib import Path

import numpy as np
from PIL import Image


SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".npy"}
# Person 1 intentionally preserves the source pixel grid. Large, legitimate
# GeoTIFFs can therefore exceed Pillow's photography-oriented default while
# still remaining within the backend's upload limit. Keep a finite safety cap.
Image.MAX_IMAGE_PIXELS = 300_000_000


def _to_uint8(array: np.ndarray) -> np.ndarray:
    """Convert image data to model-friendly uint8 RGB without changing its grid."""
    if array.dtype == np.uint8:
        return array
    values = np.asarray(array, dtype=np.float32)
    finite = np.isfinite(values)
    if not finite.any():
        raise ValueError("The input image contains no finite pixel values.")
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    if values.min() >= 0.0 and values.max() <= 1.0:
        values = values * 255.0
    elif values.min() < 0.0 or values.max() > 255.0:
        low, high = np.percentile(values[finite], [1, 99])
        if high <= low:
            raise ValueError("The input image has no usable intensity range.")
        values = (values - low) * (255.0 / (high - low))
    return np.clip(values, 0, 255).astype(np.uint8)


def _normalise_channels(array: np.ndarray) -> np.ndarray:
    """Return H x W x 3 RGB, accepting grayscale, RGBA, or band-first arrays."""
    array = np.asarray(array)
    if array.ndim == 2:
        array = np.repeat(array[:, :, None], 3, axis=2)
    elif array.ndim == 3 and array.shape[-1] not in (1, 3, 4) and array.shape[0] in (1, 3, 4):
        # Common GeoTIFF/NumPy layout: channels x height x width.
        array = np.moveaxis(array, 0, -1)
    if array.ndim != 3 or array.shape[-1] not in (1, 3, 4):
        raise ValueError(f"Expected an RGB-like image; received shape {array.shape}.")
    if array.shape[-1] == 1:
        array = np.repeat(array, 3, axis=2)
    return array[:, :, :3]


def load_rgb_image(path: str | Path) -> np.ndarray:
    """Load an image as H x W x 3 uint8 RGB; never flip, rotate, or swap BGR."""
    image_path = Path(path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Input image not found: {image_path}")
    if image_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported input format: {image_path.suffix}")

    if image_path.suffix.lower() == ".npy":
        array = np.load(image_path, allow_pickle=False)
        return np.ascontiguousarray(_to_uint8(_normalise_channels(array)))

    # Pillow exposes PNG/JPEG/TIFF channels in RGB order after convert("RGB").
    with Image.open(image_path) as image:
        return np.ascontiguousarray(np.asarray(image.convert("RGB"), dtype=np.uint8))


def load_valid_mask(path: str | Path, expected_shape: tuple[int, int]) -> np.ndarray:
    """Load a boolean H x W mask and fail clearly if it cannot align with depth."""
    mask_path = Path(path)
    if not mask_path.is_file():
        raise FileNotFoundError(f"Validity mask not found: {mask_path}")
    mask = np.load(mask_path, allow_pickle=False)
    if mask.shape != expected_shape:
        raise ValueError(
            f"Mask shape {mask.shape} does not match image/depth shape {expected_shape}."
        )
    return mask.astype(bool, copy=False)
