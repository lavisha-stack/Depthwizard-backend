"""Fast sanity checks that do not download neural-network weights."""

from pathlib import Path
import sys

import numpy as np
import pytest
from PIL import Image

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from src.image_loader import load_rgb_image, load_valid_mask
from src.output import _depth_preview, save_outputs
from src.postprocessing import resize_depth, validate_and_mask_depth
import src.inference as inference


def test_rgb_orientation_and_final_shape(tmp_path):
    rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
    rgb[0, 0] = [255, 10, 20]
    path = tmp_path / "rgb.png"
    Image.fromarray(rgb).save(path)
    loaded = load_rgb_image(path)
    assert loaded.shape == (720, 1280, 3)
    assert loaded[0, 0].tolist() == [255, 10, 20]

    raw = np.arange(6, dtype=np.float32).reshape(2, 3)
    depth = resize_depth(raw, loaded.shape[:2])
    assert depth.shape == (720, 1280)
    assert np.isfinite(depth).sum() == depth.size


def test_saved_depth_round_trip_and_mask(tmp_path):
    rgb = np.zeros((6, 8, 3), dtype=np.uint8)
    mask = np.ones((6, 8), dtype=bool)
    mask[0, 0] = False
    depth, _ = validate_and_mask_depth(np.arange(48).reshape(6, 8), mask)
    paths = save_outputs(tmp_path / "output", rgb, depth, {"test": True})
    restored = np.load(paths["depth"], allow_pickle=False)
    assert restored.shape == (6, 8)
    assert restored.dtype == np.float32
    assert np.isnan(restored[0, 0])
    heightmap = __import__("json").loads(paths["heightmap"].read_text(encoding="utf-8"))
    assert heightmap["valid"][0] is False


def test_mask_shape_error(tmp_path):
    path = tmp_path / "valid_mask.npy"
    np.save(path, np.ones((5, 7), dtype=bool))
    with pytest.raises(ValueError, match="does not match"):
        load_valid_mask(path, (6, 8))


def test_depth_preview_uses_robust_contrast_with_outliers():
    regular = np.arange(100, dtype=np.float32)
    depth = np.append(regular, 1_000_000).reshape(1, 101)
    preview = _depth_preview(depth)
    # A min/max stretch would collapse 50 to almost black. Percentile display
    # normalization preserves useful contrast without changing the raw depth.
    assert 100 < int(preview[0, 50]) < 170
    assert preview[0, -1] == 255
    assert depth[0, -1] == 1_000_000


def test_overlapping_tiles_preserve_detail_and_scene_scale(monkeypatch):
    height, width = 96, 128
    gradient = np.linspace(0, 255, height * width, dtype=np.uint8).reshape(height, width)
    rgb = np.repeat(gradient[:, :, None], 3, axis=2)

    def fake_prediction(image, loaded):
        return image[:, :, 0].astype(np.float32), image.shape[:2]

    monkeypatch.setattr(inference, "_predict_single", fake_prediction)
    predicted, model_shape, details = inference.predict_relative_depth(
        rgb,
        object(),
        tile_size=48,
        overlap=8,
        single_pass_limit=32,
    )
    assert predicted.shape == (height, width)
    assert model_shape == (48, 48)
    assert details["inference_mode"] == "seam_blended_tiles_with_global_alignment"
    assert details["tile_count"] == 9
    assert np.mean(np.abs(predicted - gradient)) < 0.01
