"""Resize, validate, and optionally mask raw relative-depth predictions."""

import warnings

import numpy as np
from PIL import Image


def _finite_stats(depth: np.ndarray) -> dict:
    """Compute stable statistics in row blocks without a full-size copy."""
    count = 0
    total = 0.0
    total_squares = 0.0
    minimum = float("inf")
    maximum = float("-inf")
    for start in range(0, depth.shape[0], 1024):
        block = depth[start : start + 1024]
        values = block[np.isfinite(block)].astype(np.float64, copy=False)
        if not values.size:
            continue
        count += int(values.size)
        total += float(values.sum(dtype=np.float64))
        total_squares += float(np.square(values).sum(dtype=np.float64))
        minimum = min(minimum, float(values.min()))
        maximum = max(maximum, float(values.max()))
    if not count:
        raise ValueError("No valid depth pixels remain after applying the mask.")
    mean = total / count
    variance = max(0.0, total_squares / count - mean * mean)
    return {
        "min_depth": minimum,
        "max_depth": maximum,
        "mean_depth": mean,
        "std_depth": float(np.sqrt(variance)),
        "finite_pixel_count": count,
        "invalid_pixel_count": int(depth.size - count),
    }


def resize_depth(depth: np.ndarray, output_shape: tuple[int, int]) -> np.ndarray:
    """Bilinearly resize continuous depth to (height, width)."""
    if depth.shape == output_shape:
        return np.asarray(depth, dtype=np.float32)
    output_height, output_width = output_shape
    float_image = Image.fromarray(np.asarray(depth, dtype=np.float32), mode="F")
    resized = float_image.resize((output_width, output_height), resample=Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.float32)


def validate_and_mask_depth(
    depth: np.ndarray, valid_mask: np.ndarray | None = None
) -> tuple[np.ndarray, dict]:
    """Validate output, clean non-finite predictions, and mark nodata as NaN."""
    depth = np.array(depth, dtype=np.float32, copy=True)
    if depth.ndim != 2 or depth.size == 0:
        raise ValueError(f"Depth output must be a non-empty 2D array; got {depth.shape}.")
    if valid_mask is not None and valid_mask.shape != depth.shape:
        raise ValueError(f"Mask shape {valid_mask.shape} does not match depth {depth.shape}.")

    model_invalid = ~np.isfinite(depth)
    if model_invalid.any():
        finite = depth[~model_invalid]
        if finite.size == 0:
            raise ValueError("The model produced no finite depth values.")
        replacement = float(np.median(finite))
        warnings.warn(
            f"Model produced {model_invalid.sum()} invalid values; replacing them with "
            f"the finite median ({replacement:.6g}).",
            RuntimeWarning,
        )
        depth[model_invalid] = replacement

    if valid_mask is not None:
        depth[~valid_mask] = np.nan
    stats = _finite_stats(depth)
    if stats["std_depth"] == 0.0:
        warnings.warn("The model produced a constant depth map.", RuntimeWarning)
    return depth, stats
