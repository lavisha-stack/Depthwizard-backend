"""Save raw numerical output, human previews, and handoff metadata."""

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def _depth_preview(depth: np.ndarray) -> np.ndarray:
    """Create a robust grayscale preview; invalid pixels remain black.

    A raw min/max stretch lets a handful of extreme pixels flatten the visible
    contrast, which is especially common in large scenes. The numerical depth
    array remains untouched; only this display preview uses percentile limits.
    """
    preview = np.zeros(depth.shape, dtype=np.uint8)
    # Estimate display limits from a bounded deterministic sample. The full
    # float32 depth can exceed a gigabyte even though the uploaded TIFF is much
    # smaller, so copying every finite value just for a preview is unsafe.
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
        # Blend a modest histogram equalization into the linear percentile
        # stretch. This makes subtle roof/canopy structure readable without
        # replacing the numerical depth values used by calibration and 3D.
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
        # Aerial relative-depth predictions often carry a broad brightness
        # slope that hides roofs and tree crowns in a global grayscale stretch.
        # Blend in a locally detrended display layer. This changes only the PNG
        # preview; relative_depth.npy and the 3D height samples stay untouched.
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


def _heightmap_payload(depth: np.ndarray, max_size: int = 512) -> dict:
    """Create a browser-friendly, bounded JSON grid for the 3D viewer."""
    height, width = depth.shape
    scale = min(1.0, max_size / max(width, height))
    out_width = max(2, round(width * scale))
    out_height = max(2, round(height * scale))
    finite_source = np.isfinite(depth)
    if not finite_source.any():
        raise ValueError("Cannot export a 3D heightmap without finite depth samples.")
    fill = float(np.nanmedian(depth))
    filled = np.nan_to_num(depth, nan=fill, posinf=fill, neginf=fill).astype(np.float32)
    # Continuous downsampling avoids the terracing/aliasing produced by taking
    # one nearest source pixel for every browser vertex.
    sampled = np.asarray(
        Image.fromarray(filled, mode="F").resize(
            (out_width, out_height), Image.Resampling.BILINEAR
        ),
        dtype=np.float32,
    )
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
        "elevation_min": float(sampled.min()),
        "elevation_max": float(sampled.max()),
        "nodata": None,
        "units": "relative",
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
        json.dumps(_heightmap_payload(depth), separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return {name: path for name, path in paths.items() if path.is_file()}
