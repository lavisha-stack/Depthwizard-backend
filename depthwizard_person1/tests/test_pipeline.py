"""Small synthetic sanity tests; no external imagery is required."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from PIL import Image
from rasterio.transform import from_origin

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from src.coordinates import map_to_pixel, pixel_to_map  # noqa: E402
from src.image_loader import load_image  # noqa: E402


class Person1PipelineTests(unittest.TestCase):
    def test_png_is_not_georeferenced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "plain.png"
            Image.fromarray(np.full((5, 7, 3), 100, dtype=np.uint8)).save(path)
            loaded = load_image(path)
            self.assertFalse(loaded.metadata["is_georeferenced"])
            self.assertIsNone(loaded.metadata["crs"])
            self.assertEqual(loaded.original_rgb.shape, (5, 7, 3))
            self.assertTrue(loaded.valid_mask.all())

    def test_non_georeferenced_tiff_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "plain.tif"
            with rasterio.open(
                path, "w", driver="GTiff", width=4, height=3, count=3, dtype="uint8"
            ) as dataset:
                dataset.write(np.ones((3, 3, 4), dtype=np.uint8))
            loaded = load_image(path)
            self.assertFalse(loaded.metadata["is_georeferenced"])
            self.assertEqual(loaded.original_rgb.shape, (3, 4, 3))

    def test_geotiff_round_trip_and_cli_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            path = root / "geo.tif"
            output = root / "out"
            transform = from_origin(500000, 2000000, 2, 2)
            data = np.arange(3 * 6 * 8, dtype=np.uint16).reshape(3, 6, 8)
            data[:, 0, 0] = 65535
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                width=8,
                height=6,
                count=3,
                dtype="uint16",
                crs="EPSG:32644",
                transform=transform,
                nodata=65535,
            ) as dataset:
                dataset.write(data)

            loaded = load_image(path)
            self.assertTrue(loaded.metadata["is_georeferenced"])
            self.assertEqual(loaded.original_rgb.shape, (6, 8, 3))
            self.assertFalse(loaded.valid_mask[0, 0])

            row, col = 3, 4
            x, y = pixel_to_map(row, col, transform)
            recovered_row, recovered_col = map_to_pixel(x, y, transform)
            self.assertAlmostEqual(row, recovered_row)
            self.assertAlmostEqual(col, recovered_col)

            result = subprocess.run(
                [sys.executable, str(PROJECT_DIR / "main.py"), "--input", str(path), "--output", str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = {"rgb_original.npy", "rgb_model.png", "valid_mask.npy", "metadata.json", "preview.png"}
            self.assertEqual(expected, {item.name for item in output.iterdir()})
            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["transform"], [2.0, 0.0, 500000.0, 0.0, -2.0, 2000000.0])
            self.assertEqual(np.load(output / "rgb_original.npy").shape, (6, 8, 3))

    def test_large_scan_border_and_invalid_crs_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "scanned.tif"
            data = np.zeros((3, 100, 120), dtype=np.uint8)
            data[:, 8:92, 10:110] = 120
            data[0, 2:5, 2:5] = 255  # bright film annotation in black border
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                width=120,
                height=100,
                count=3,
                dtype="uint8",
                crs="EPSG:26916",
                transform=from_origin(744000, -3700000, 1, 1),
            ) as dataset:
                dataset.write(data)

            loaded = load_image(path, max_model_size=60)
            self.assertEqual(loaded.original_rgb.shape, (50, 60, 3))
            self.assertFalse(loaded.metadata["is_georeferenced"])
            self.assertIn("outside", loaded.metadata["georeference_warning"])
            self.assertTrue(loaded.metadata["inferred_border_nodata"])
            self.assertFalse(loaded.valid_mask[0, 0])
            self.assertTrue(loaded.valid_mask[25, 30])
            self.assertLess(loaded.metadata["valid_fraction"], 0.9)


if __name__ == "__main__":
    unittest.main()
