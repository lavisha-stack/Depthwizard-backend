"""Export calibrated elevation products without losing the source grid."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import rasterio

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _json_default(value: Any):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__} to JSON")


def write_json(path: str | Path, value: Any) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=_json_default) + "\n",
        encoding="utf-8",
    )
    return output


def write_dsm(path: str | Path, values: np.ndarray, target, nodata: float) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(values, dtype=np.float32)
    with rasterio.open(
        output,
        "w",
        driver="GTiff",
        width=target.width,
        height=target.height,
        count=1,
        dtype="float32",
        crs=target.crs,
        transform=target.transform,
        nodata=nodata,
        compress="deflate",
        predictor=3,
        tiled=True,
        BIGTIFF="IF_SAFER",
    ) as dataset:
        # Write one tiled window at a time so a large DSM does not require a
        # second full-resolution in-memory copy merely for nodata conversion.
        for _, window in dataset.block_windows(1):
            rows, columns = window.toslices()
            block = data[rows, columns]
            stored = np.where(np.isfinite(block), block, nodata).astype(np.float32)
            dataset.write(stored, 1, window=window)
        dataset.set_band_description(1, "estimated surface elevation (metres)")
        dataset.update_tags(units="metre", product="estimated/fused DSM")
    return output


def write_preview(path: str | Path, values: np.ndarray) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Percentiles and plotting only need a display sample. Bounding this grid
    # keeps previews reliable for very large (hundreds-of-megabytes) rasters.
    step = max(1, int(np.ceil(max(values.shape) / 2048)))
    display = np.asarray(values[::step, ::step], dtype=np.float32)
    finite = display[np.isfinite(display)]
    if finite.size == 0:
        raise ValueError("Cannot write a DSM preview without finite elevations.")
    low, high = np.percentile(finite, (2.0, 98.0))
    if high <= low:
        high = low + 1.0
    figure, axis = plt.subplots(figsize=(9, 7), constrained_layout=True)
    image = axis.imshow(display, cmap="terrain", vmin=low, vmax=high)
    axis.set_title("Estimated surface elevation")
    axis.set_axis_off()
    colorbar = figure.colorbar(image, ax=axis, shrink=0.82)
    colorbar.set_label("Elevation (m)")
    figure.savefig(output, dpi=140)
    plt.close(figure)
    return output
