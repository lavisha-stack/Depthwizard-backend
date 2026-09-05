"""Combine a coarse elevation baseline with calibrated monocular detail."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter


def _smooth_finite(values: np.ndarray, sigma: float) -> np.ndarray:
    valid = np.isfinite(values)
    numerator = gaussian_filter(np.where(valid, values, 0.0).astype(np.float32), sigma=sigma, mode="nearest")
    denominator = gaussian_filter(valid.astype(np.float32), sigma=sigma, mode="nearest")
    output = np.full(values.shape, np.nan, dtype=np.float32)
    usable = denominator > 1e-6
    output[usable] = numerator[usable] / denominator[usable]
    return output


def fuse_srtm_and_depth(
    calibrated_depth: np.ndarray,
    aligned_srtm: np.ndarray,
    sigma_pixels: float,
    alpha: float,
) -> tuple[np.ndarray, dict]:
    if calibrated_depth.shape != aligned_srtm.shape:
        raise ValueError("Calibrated depth and aligned SRTM shapes do not match.")
    if alpha < 0:
        raise ValueError("Fusion alpha must be non-negative.")
    sigma = max(float(sigma_pixels), 0.01)
    smooth_depth = _smooth_finite(calibrated_depth, sigma)
    smooth_srtm = _smooth_finite(aligned_srtm, sigma)
    valid = np.isfinite(calibrated_depth) & np.isfinite(smooth_depth) & np.isfinite(smooth_srtm)
    final = np.full(calibrated_depth.shape, np.nan, dtype=np.float32)
    detail = calibrated_depth - smooth_depth
    final[valid] = smooth_srtm[valid] + float(alpha) * detail[valid]
    if not np.isfinite(final).any():
        raise ValueError("Fusion produced no finite elevation values.")
    return final, {"sigma_pixels": sigma, "alpha": float(alpha), "valid_pixels": int(valid.sum())}
