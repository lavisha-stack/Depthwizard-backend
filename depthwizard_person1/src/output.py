"""Write the stable hand-off files used by Persons 2 and 3."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _json_default(value: Any) -> Any:
    """Convert NumPy scalar values that JSON does not understand directly."""
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Cannot serialize {type(value).__name__} to JSON")


def write_outputs(
    output_dir: Path,
    original_rgb: np.ndarray,
    model_rgb: np.ndarray,
    valid_mask: np.ndarray,
    metadata: dict[str, Any],
    preview_max_size: tuple[int, int],
    save_original_array: bool = True,
) -> None:
    """Write arrays, model PNG, metadata, and a lightweight preview."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if save_original_array:
        np.save(output_dir / "rgb_original.npy", original_rgb, allow_pickle=False)
    np.save(output_dir / "valid_mask.npy", valid_mask.astype(bool), allow_pickle=False)

    model_image = Image.fromarray(model_rgb, mode="RGB")
    model_image.save(output_dir / "rgb_model.png")

    preview = model_image.copy()
    preview.thumbnail(preview_max_size, Image.Resampling.LANCZOS)
    preview.save(output_dir / "preview.png")

    with (output_dir / "metadata.json").open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2, default=_json_default, allow_nan=False)
        file.write("\n")
