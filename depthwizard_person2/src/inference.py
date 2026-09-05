"""Resolution-aware monocular inference for large aerial images."""

from __future__ import annotations

import math
from contextlib import nullcontext

import numpy as np
from PIL import Image

from .depth_model import LoadedDepthModel


def _predict_single(rgb_image: np.ndarray, loaded: LoadedDepthModel) -> tuple[np.ndarray, tuple[int, int]]:
    """Run one model forward pass and return its native 2-D prediction."""
    import torch

    pil_image = Image.fromarray(rgb_image, mode="RGB")
    inputs = loaded.processor(images=pil_image, return_tensors="pt")
    pixel_values = inputs["pixel_values"]
    model_input_hw = (int(pixel_values.shape[-2]), int(pixel_values.shape[-1]))
    inputs = {name: tensor.to(loaded.device) for name, tensor in inputs.items()}
    autocast = (
        torch.autocast(device_type="cuda", dtype=torch.float16)
        if loaded.device.type == "cuda"
        else nullcontext()
    )
    try:
        with torch.inference_mode(), autocast:
            predicted = loaded.model(**inputs).predicted_depth
    except torch.cuda.OutOfMemoryError as exc:
        torch.cuda.empty_cache()
        raise RuntimeError(
            "The GPU ran out of memory during depth inference. Use the Small model "
            "or reduce MODEL_MAX_SIZE before retrying."
        ) from exc
    raw = predicted.detach().float().cpu().numpy().squeeze()
    if raw.ndim != 2:
        raise RuntimeError(f"Expected a 2D depth prediction; model returned {raw.shape}.")
    return np.asarray(raw, dtype=np.float32), model_input_hw


def _resize_float(values: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if values.shape == shape:
        return np.asarray(values, dtype=np.float32)
    height, width = shape
    image = Image.fromarray(np.asarray(values, dtype=np.float32), mode="F")
    return np.asarray(image.resize((width, height), Image.Resampling.BILINEAR), dtype=np.float32)


def _fill_invalid_rgb(rgb: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    """Replace masked border pixels for inference without changing the mask."""
    if mask is None or bool(np.all(mask)):
        return rgb
    prepared = np.array(rgb, copy=True)
    height, width = mask.shape
    # Scanline extension is inexpensive and avoids giving the model a false
    # black cliff around scanned aerial photographs.
    for row in range(height):
        valid = np.flatnonzero(mask[row])
        if valid.size:
            first, last = int(valid[0]), int(valid[-1])
            prepared[row, :first] = prepared[row, first]
            prepared[row, last + 1:] = prepared[row, last]
    for col in range(width):
        valid = np.flatnonzero(mask[:, col])
        if valid.size:
            first, last = int(valid[0]), int(valid[-1])
            prepared[:first, col] = prepared[first, col]
            prepared[last + 1:, col] = prepared[last, col]
    remaining = ~mask
    if remaining.any():
        sample_stride = max(1, math.ceil(math.sqrt(mask.size / 500_000)))
        sample_rgb = prepared[::sample_stride, ::sample_stride]
        sample_mask = mask[::sample_stride, ::sample_stride]
        fill = np.median(sample_rgb[sample_mask], axis=0).astype(np.uint8)
        prepared[remaining] = fill
    return prepared


def _tile_starts(length: int, tile_size: int, overlap: int) -> list[int]:
    if length <= tile_size:
        return [0]
    stride = tile_size - overlap
    starts = list(range(0, length - tile_size + 1, stride))
    final = length - tile_size
    if starts[-1] != final:
        starts.append(final)
    return starts


def _align_to_global(local: np.ndarray, reference: np.ndarray, valid_mask: np.ndarray | None) -> np.ndarray:
    """Align a tile's arbitrary scale/shift to the scene-wide prediction."""
    valid = np.isfinite(local) & np.isfinite(reference)
    if valid_mask is not None:
        valid &= valid_mask
    rows, cols = np.nonzero(valid)
    if rows.size < 64:
        return reference
    stride = max(1, math.ceil(rows.size / 100_000))
    x = local[rows[::stride], cols[::stride]].astype(np.float64)
    y = reference[rows[::stride], cols[::stride]].astype(np.float64)
    x_low, x_high = np.percentile(x, (2, 98))
    y_low, y_high = np.percentile(y, (2, 98))
    keep = (x >= x_low) & (x <= x_high) & (y >= y_low) & (y <= y_high)
    x, y = x[keep], y[keep]
    variance = float(np.var(x))
    if x.size < 32 or variance < 1e-12:
        return reference
    slope = float(np.cov(x, y, bias=True)[0, 1] / variance)
    if not math.isfinite(slope) or slope <= 0:
        slope = float(np.std(y) / max(np.std(x), 1e-6))
    slope = float(np.clip(slope, 0.1, 10.0))
    offset = float(np.median(y - slope * x))
    return np.asarray(local * slope + offset, dtype=np.float32)


def _merge_local_detail(aligned: np.ndarray, reference: np.ndarray, overlap: int) -> np.ndarray:
    """Add only a tile's high-frequency detail to the global prediction.

    Independent monocular predictions have arbitrary low-frequency bias. If
    whole aligned tiles are blended, that bias remains visible as rectangles.
    Removing each tile's coarse component makes the scene-wide pass solely
    responsible for the continuous baseline while retaining local object edges.
    """
    reference_range = max(float(np.ptp(reference)), 1e-6)
    if float(np.mean(np.abs(aligned - reference))) <= reference_range * 1e-6:
        return reference
    radius = max(4, min(aligned.shape) // 16)
    local_low_frequency = _box_blur(aligned, radius)
    detail = np.asarray(aligned - local_low_frequency, dtype=np.float32)
    finite = detail[np.isfinite(detail)]
    if not finite.size:
        return reference
    detail -= float(np.median(finite))
    limit = float(np.percentile(np.abs(finite), 99.5))
    if not math.isfinite(limit) or limit <= 1e-8:
        return reference
    detail = np.clip(detail, -limit, limit)
    taper_size = min(overlap, aligned.shape[0] // 3, aligned.shape[1] // 3)
    if taper_size > 0:
        ramp = np.sin(np.linspace(0, math.pi / 2, taper_size, dtype=np.float32)) ** 2
        vertical = np.ones(aligned.shape[0], dtype=np.float32)
        horizontal = np.ones(aligned.shape[1], dtype=np.float32)
        vertical[:taper_size] = ramp; vertical[-taper_size:] = ramp[::-1]
        horizontal[:taper_size] = ramp; horizontal[-taper_size:] = ramp[::-1]
        detail *= vertical[:, None] * horizontal[None, :]
    return np.asarray(reference + detail, dtype=np.float32)


def _box_blur(values: np.ndarray, radius: int) -> np.ndarray:
    """Separable reflected-edge box blur for float depth without SciPy."""
    result = np.asarray(values, dtype=np.float32)
    window = radius * 2 + 1
    for axis in (1, 0):
        padding = [(0, 0), (0, 0)]
        padding[axis] = (radius, radius)
        padded = np.pad(result, padding, mode="reflect")
        prefix_shape = list(padded.shape)
        prefix_shape[axis] = 1
        prefix = np.concatenate(
            [np.zeros(prefix_shape, dtype=np.float32), np.cumsum(padded, axis=axis, dtype=np.float32)],
            axis=axis,
        )
        high = [slice(None), slice(None)]
        low = [slice(None), slice(None)]
        high[axis] = slice(window, window + result.shape[axis])
        low[axis] = slice(0, result.shape[axis])
        result = (prefix[tuple(high)] - prefix[tuple(low)]) / window
    return np.asarray(result, dtype=np.float32)


def _blend_weights(
    height: int,
    width: int,
    top: int,
    left: int,
    image_height: int,
    image_width: int,
) -> np.ndarray:
    vertical = np.maximum(np.hanning(height).astype(np.float32), 0.05)
    horizontal = np.maximum(np.hanning(width).astype(np.float32), 0.05)
    if top == 0:
        vertical[: max(1, height // 8)] = 1
    if top + height == image_height:
        vertical[-max(1, height // 8):] = 1
    if left == 0:
        horizontal[: max(1, width // 8)] = 1
    if left + width == image_width:
        horizontal[-max(1, width // 8):] = 1
    return vertical[:, None] * horizontal[None, :]


def predict_relative_depth(
    rgb_image: np.ndarray,
    loaded: LoadedDepthModel,
    valid_mask: np.ndarray | None = None,
    *,
    tile_size: int = 768,
    overlap: int = 128,
    single_pass_limit: int = 1024,
) -> tuple[np.ndarray, tuple[int, int], dict]:
    """Predict relative depth, tiling large aerial scenes with overlap.

    A global low-resolution pass provides consistent scene-wide scale. Local
    passes recover roofs, roads, and canopy boundaries; each is linearly aligned
    to the global prediction before cosine-weighted stitching.
    """
    if rgb_image.ndim != 3 or rgb_image.shape[2] != 3:
        raise ValueError(f"Expected H x W x 3 RGB input, got {rgb_image.shape}.")
    if valid_mask is not None and valid_mask.shape != rgb_image.shape[:2]:
        raise ValueError("Validity mask dimensions do not match the RGB image.")
    if overlap < 0 or tile_size <= overlap:
        raise ValueError("Tile size must be positive and larger than overlap.")

    prepared = _fill_invalid_rgb(rgb_image, valid_mask)
    height, width = prepared.shape[:2]
    if max(height, width) <= single_pass_limit:
        raw, model_input_hw = _predict_single(prepared, loaded)
        return raw, model_input_hw, {
            "inference_mode": "single_pass",
            "tile_count": 1,
            "working_width": width,
            "working_height": height,
        }

    global_raw, global_input_hw = _predict_single(prepared, loaded)
    global_depth = _resize_float(global_raw, (height, width))
    tile_height, tile_width = min(tile_size, height), min(tile_size, width)
    row_starts = _tile_starts(height, tile_height, min(overlap, tile_height - 1))
    col_starts = _tile_starts(width, tile_width, min(overlap, tile_width - 1))
    accumulated = np.zeros((height, width), dtype=np.float32)
    weight_sum = np.zeros((height, width), dtype=np.float32)
    model_input_hw = global_input_hw

    for top in row_starts:
        for left in col_starts:
            bottom, right = top + tile_height, left + tile_width
            local_raw, model_input_hw = _predict_single(prepared[top:bottom, left:right], loaded)
            local = _resize_float(local_raw, (tile_height, tile_width))
            local_mask = valid_mask[top:bottom, left:right] if valid_mask is not None else None
            aligned = _align_to_global(local, global_depth[top:bottom, left:right], local_mask)
            enhanced = _merge_local_detail(aligned, global_depth[top:bottom, left:right], overlap)
            weights = _blend_weights(tile_height, tile_width, top, left, height, width)
            accumulated[top:bottom, left:right] += enhanced * weights
            weight_sum[top:bottom, left:right] += weights

    stitched = np.divide(
        accumulated,
        weight_sum,
        out=global_depth.copy(),
        where=weight_sum > 1e-8,
    )
    # Even with overlap and tapering, independent local predictions can leave
    # a one-pixel derivative discontinuity where one tile ceases to contribute.
    # Smooth only the stitched *detail residual*, not the scene-wide baseline.
    # A five-pixel kernel is negligible relative to a 768-pixel tile but makes
    # the grid boundaries no sharper than ordinary neighbouring gradients.
    stitched_detail = _box_blur(stitched - global_depth, radius=2)
    stitched = global_depth + stitched_detail
    return stitched.astype(np.float32, copy=False), model_input_hw, {
        "inference_mode": "seam_blended_tiles_with_global_alignment",
        "tile_count": len(row_starts) * len(col_starts),
        "tile_width": tile_width,
        "tile_height": tile_height,
        "tile_overlap": overlap,
        "working_width": width,
        "working_height": height,
    }
