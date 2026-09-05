"""Save raw numerical output, human previews, and handoff metadata."""

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def _depth_preview(depth: np.ndarray) -> np.ndarray:
    """Create a robust grayscale preview; invalid pixels remain black."""
    preview = np.zeros(depth.shape, dtype=np.uint8)
    stride = max(1, int(np.ceil(np.sqrt(depth.size / 2_000_000))))
    sample = depth[::stride, ::stride]
    sample_values = sample[np.isfinite(sample)]
    if sample_values.size:
        low, high = np.percentile(sample_values, (2.0, 98.0))
    else:
        low = high = 0.0
    histogram = np.zeros(256, dtype=np.int64)
    if high > low:
        for start in range(0, depth.shape[0], 1024):
            block = depth[start : start + 1024]
            finite = np.isfinite(block)
            if not finite.any():
                continue
            scaled = np.clip((block - low) / (high - low), 0.0, 1.0)
            preview_block = preview[start : start + 1024]
            preview_block[finite] = np.round(scaled[finite] * 255.0).astype(np.uint8)
            histogram += np.bincount(preview_block[finite], minlength=256)
        cumulative = np.cumsum(histogram)
        occupied = np.flatnonzero(histogram)
        if occupied.size and cumulative[-1] > histogram[occupied[0]]:
            minimum = cumulative[occupied[0]]
            equalized = np.clip((cumulative - minimum) * 255.0 / (cumulative[-1] - minimum), 0, 255)
            lut = np.round(0.7 * np.arange(256) + 0.3 * equalized).astype(np.uint8)
            for start in range(0, depth.shape[0], 1024):
                block = depth[start : start + 1024]
                finite = np.isfinite(block)
                preview_block = preview[start : start + 1024]
                preview_block[finite] = lut[preview_block[finite]]
        if min(depth.shape) >= 128:
            radius = max(4.0, min(depth.shape) / 96.0)
            blurred = np.asarray(
                Image.fromarray(preview, mode="L").filter(ImageFilter.GaussianBlur(radius=radius)),
                dtype=np.float32,
            )
            detail = preview.astype(np.float32) - blurred
            valid_detail = detail[np.isfinite(depth)]
            detail_low, detail_high = np.percentile(valid_detail, (1.0, 99.0))
            if detail_high > detail_low:
                local = np.clip((detail - detail_low) / (detail_high - detail_low), 0.0, 1.0) * 255.0
                finite = np.isfinite(depth)
                preview[finite] = np.round(
                    0.68 * preview[finite].astype(np.float32) + 0.32 * local[finite]
                ).astype(np.uint8)
    return preview


def _robust_relative_height(depth: np.ndarray, larger_value_means: str = "closer") -> np.ndarray:
    """Convert monocular inverse-depth into a stable viewer height field.

    Depth Anything V2 produces relative inverse depth: larger values represent
    nearer surfaces. That is the opposite of a terrain height field. Feeding
    the raw prediction directly to Three.js therefore makes nearby roofs and
    walls rise in the wrong direction and exaggerates the scene.

    This conversion is intentionally applied only to the browser heightmap;
    the original relative_depth.npy remains untouched for later calibration.
    We also use percentile clipping so a few extreme predictions cannot set
    the entire viewer's vertical scale.
    """
    values = np.asarray(depth, dtype=np.float32)
    finite = np.isfinite(values)
    if not finite.any():
        raise ValueError("Cannot create a height field without finite depth samples.")

    valid_values = values[finite]
    low, high = np.percentile(valid_values, (2.0, 98.0))
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        low = float(valid_values.min())
        high = float(valid_values.max())
    if high <= low:
        return np.zeros_like(values, dtype=np.float32)

    clipped = np.clip(values, low, high)
    normalized = (clipped - low) / (high - low)
    if larger_value_means.strip().lower() == "closer":
        normalized = 1.0 - normalized

    # A very light blur suppresses single-pixel depth spikes that become
    # unnatural needles/walls after vertical displacement, while preserving
    # buildings, ridges and other structures at terrain-viewer resolution.
    if min(values.shape) >= 64:
        smoothed = np.asarray(
            Image.fromarray(normalized.astype(np.float32), mode="F").filter(
                ImageFilter.GaussianBlur(radius=0.8)
            ),
            dtype=np.float32,
        )
        normalized = 0.72 * normalized + 0.28 * smoothed

    fill = float(np.nanmedian(normalized))
    normalized = np.nan_to_num(normalized, nan=fill, posinf=fill, neginf=fill)
    return np.clip(normalized, 0.0, 1.0).astype(np.float32)


def _heightmap_payload(
    depth: np.ndarray,
    max_size: int = 512,
    larger_value_means: str = "closer",
) -> dict:
    """Create a browser-friendly, bounded terrain height field."""
    height, width = depth.shape
    scale = min(1.0, max_size / max(width, height))
    out_width = max(2, round(width * scale))
    out_height = max(2, round(height * scale))

    terrain_height = _robust_relative_height(depth, larger_value_means)
    sampled = np.asarray(
        Image.fromarray(terrain_height, mode="F").resize(
            (out_width, out_height), Image.Resampling.BILINEAR
        ),
        dtype=np.float32,
    )

    finite_source = np.isfinite(depth)
    finite = np.asarray(
        Image.fromarray(finite_source.astype(np.uint8) * 255, mode="L").resize(
            (out_width, out_height), Image.Resampling.NEAREST
        ),
        dtype=np.uint8,
    ) > 0

    return {
        "width": out_width,
        "height": out_height,
        "heights": sampled.ravel().tolist(),
        "valid": finite.ravel().tolist(),
        "elevation_min": 0.0,
        "elevation_max": 1.0,
        "nodata": None,
        "units": "relative",
        "height_semantics": "normalized_terrain_height",
        "source_depth_semantics": "relative_inverse_depth",
    }


def save_outputs(
    output_dir: str | Path,
    rgb_image: np.ndarray,
    depth: np.ndarray,
    metadata: dict,
    save_input_preview: bool = True,
) -> dict[str, Path]:
    """Write all required Person 2 artifacts and return their paths."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "depth": directory / "relative_depth.npy",
        "preview": directory / "relative_depth_preview.png",
        "metadata": directory / "depth_metadata.json",
        "input_preview": directory / "input_preview.png",
        "heightmap": directory / "heightmap.json",
    }
    np.save(paths["depth"], depth, allow_pickle=False)
    Image.fromarray(_depth_preview(depth), mode="L").save(paths["preview"])
    if save_input_preview:
        Image.fromarray(rgb_image, mode="RGB").save(paths["input_preview"])
    paths["metadata"].write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    paths["heightmap"].write_text(
        json.dumps(
            _heightmap_payload(
                depth,
                larger_value_means=metadata.get("larger_value_means", "closer"),
            ),
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return {name: path for name, path in paths.items() if path.is_file()}
