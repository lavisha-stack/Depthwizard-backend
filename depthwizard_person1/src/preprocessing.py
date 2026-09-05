"""Convert numeric RGB imagery into a safe uint8 model image."""

from __future__ import annotations

import numpy as np


def _percentile_bounds(
    channel: np.ndarray, usable: np.ndarray, low_percentile: float, high_percentile: float
) -> tuple[float, float] | None:
    """Calculate exact integer percentiles with bounded memory; sample floats."""
    if np.issubdtype(channel.dtype, np.integer):
        info = np.iinfo(channel.dtype)
        value_range = int(info.max) - int(info.min) + 1
        if value_range <= 1_000_000:
            histogram = np.zeros(value_range, dtype=np.int64)
            for start in range(0, channel.shape[0], 1024):
                block = channel[start : start + 1024]
                mask = usable[start : start + 1024]
                if mask.any():
                    histogram += np.bincount(
                        block[mask].astype(np.int64) - int(info.min), minlength=value_range
                    )
            count = int(histogram.sum())
            if not count:
                return None
            cumulative = np.cumsum(histogram)
            low_rank = low_percentile / 100.0 * (count - 1)
            high_rank = high_percentile / 100.0 * (count - 1)

            def interpolate(rank: float) -> float:
                lower_rank, upper_rank = int(np.floor(rank)), int(np.ceil(rank))
                lower = np.searchsorted(cumulative, lower_rank + 1) + int(info.min)
                upper = np.searchsorted(cumulative, upper_rank + 1) + int(info.min)
                return float(lower + (upper - lower) * (rank - lower_rank))

            return interpolate(low_rank), interpolate(high_rank)

    # Float and very wide integer rasters use a deterministic spatial sample.
    # Two million values give stable display percentiles without multi-GB copies.
    stride = max(1, int(np.ceil(np.sqrt(channel.size / 2_000_000))))
    sampled = channel[::stride, ::stride]
    sampled_mask = usable[::stride, ::stride]
    values = sampled[sampled_mask]
    if not values.size:
        return None
    low, high = np.percentile(values, [low_percentile, high_percentile])
    return float(low), float(high)


def normalize_rgb(
    original_rgb: np.ndarray,
    valid_mask: np.ndarray,
    low_percentile: float = 2.0,
    high_percentile: float = 98.0,
) -> np.ndarray:
    """Robustly stretch each channel to 0..255 without modifying the source.

    Percentiles are calculated only from finite, valid pixels. Invalid output
    pixels become black, while their locations remain recorded in valid_mask.
    The returned shape and orientation exactly match original_rgb.
    """
    if original_rgb.ndim != 3 or original_rgb.shape[2] != 3:
        raise ValueError(f"Expected an H x W x 3 RGB array, got {original_rgb.shape}.")
    if valid_mask.shape != original_rgb.shape[:2]:
        raise ValueError("valid_mask dimensions do not match the RGB image.")
    if not 0 <= low_percentile < high_percentile <= 100:
        raise ValueError("Normalization percentiles must satisfy 0 <= low < high <= 100.")

    output = np.zeros(original_rgb.shape, dtype=np.uint8)
    for channel_index in range(3):
        channel = original_rgb[:, :, channel_index]
        usable = valid_mask & np.isfinite(channel)
        bounds = _percentile_bounds(channel, usable, low_percentile, high_percentile)
        if bounds is None:
            continue
        low, high = bounds
        if not np.isfinite(low) or not np.isfinite(high):
            continue
        if high <= low:
            # A constant non-zero channel is shown at its original uint8 value
            # when possible, or white for larger numeric types.
            constant_value = 0 if high == 0 else min(255, int(round(high)))
            output[:, :, channel_index][usable] = constant_value
            continue
        for start in range(0, channel.shape[0], 1024):
            stop = start + 1024
            block_mask = usable[start:stop]
            if not block_mask.any():
                continue
            block = channel[start:stop].astype(np.float32, copy=False)
            scaled = np.clip((block - low) / (high - low), 0.0, 1.0)
            output_block = output[start:stop, :, channel_index]
            output_block[block_mask] = np.round(scaled[block_mask] * 255).astype(np.uint8)
    return output
