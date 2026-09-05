"""Synthetic tests for calibration, alignment, fusion, and export."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from src.calibration import extract_gcp_pairs, fit_candidate_models  # noqa: E402
from src.io_utils import derive_target_grid, read_geotiff_metadata  # noqa: E402
from src.srtm import srtm_tile_names_for_wgs84_bounds  # noqa: E402
from src.validation import calculate_metrics  # noqa: E402


class Person3Tests(unittest.TestCase):
    def test_linear_and_inverse_calibration(self) -> None:
        depth = np.linspace(1.0, 10.0, 20)
        height = 3.5 * depth + 42.0
        selected, candidates = fit_candidate_models(depth, height, "linear")
        self.assertEqual(selected.model_type, "linear")
        self.assertAlmostEqual(selected.slope, 3.5, places=6)
        self.assertAlmostEqual(selected.intercept, 42.0, places=6)
        self.assertEqual({item.model_type for item in candidates}, {"linear", "inverse", "robust_linear"})

    def test_gcp_extraction_and_metrics(self) -> None:
        depth = np.arange(25, dtype=np.float32).reshape(5, 5)
        gcps = [
            {"name": "a", "row": 1, "col": 2, "elevation_m": 100},
            {"name": "b", "row": 3, "col": 4, "elevation_m": 120},
        ]
        x, y, details = extract_gcp_pairs(gcps, depth, "EPSG:4326", from_origin(0, 5, 1, 1))
        np.testing.assert_array_equal(x, [7, 19])
        np.testing.assert_array_equal(y, [100, 120])
        self.assertEqual(len(details), 2)
        metrics = calculate_metrics(np.array([[1.0, 2.0]]), np.array([[2.0, 2.0]]))
        self.assertAlmostEqual(metrics["mae_m"], 0.5)
        self.assertAlmostEqual(metrics["bias_m"], -0.5)

    def test_bounded_target_grid_preserves_extent_and_scales_pixel_gcps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scene.tif"
            with rasterio.open(
                path, "w", driver="GTiff", width=100, height=80, count=1,
                dtype="uint8", crs="EPSG:4326", transform=from_origin(77, 29, 0.001, 0.001),
            ) as dataset:
                dataset.write(np.ones((1, 80, 100), dtype=np.uint8))
            source = read_geotiff_metadata(path)
            working = derive_target_grid(source, (40, 50))
            np.testing.assert_allclose(tuple(working.bounds), tuple(source.bounds), atol=1e-10)
            self.assertEqual(working.shape, (40, 50))
            depth = np.arange(40 * 50, dtype=np.float32).reshape(40, 50)
            values, _, details = extract_gcp_pairs(
                [{"row": 79, "col": 99, "elevation_m": 200}],
                depth, working.crs, working.transform, source_shape=source.shape,
            )
            self.assertEqual(values.tolist(), [float(depth[39, 49])])
            self.assertEqual(details[0]["coordinate_source"], "source_pixel")

    def test_rejects_geographically_impossible_crs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad_crs.tif"
            with rasterio.open(
                path, "w", driver="GTiff", width=10, height=10, count=1,
                dtype="uint8", crs="EPSG:26916", transform=from_origin(744000, -3740000, 1, 1),
            ) as dataset:
                dataset.write(np.ones((1, 10, 10), dtype=np.uint8))
            with self.assertRaisesRegex(ValueError, "outside that CRS's area of use"):
                read_geotiff_metadata(path)

    def test_tile_names(self) -> None:
        self.assertEqual(
            srtm_tile_names_for_wgs84_bounds(77.1, 28.1, 78.1, 29.1),
            ["N28E077.hgt", "N28E078.hgt", "N29E077.hgt", "N29E078.hgt"],
        )

    def test_cli_with_pixel_gcps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            geotiff = root / "scene.tif"
            depth_path = root / "depth.npy"
            gcps_path = root / "gcps.csv"
            output = root / "output"
            height, width = 20, 24
            relative = np.linspace(1.0, 5.0, height * width, dtype=np.float32).reshape(height, width)
            with rasterio.open(
                geotiff,
                "w",
                driver="GTiff",
                width=width,
                height=height,
                count=3,
                dtype="uint8",
                crs="EPSG:32644",
                transform=from_origin(500000, 2000000, 2, 2),
            ) as dataset:
                dataset.write(np.full((3, height, width), 100, dtype=np.uint8))
            np.save(depth_path, relative, allow_pickle=False)
            gcps_path.write_text(
                "name,row,col,elevation_m\n"
                f"a,1,1,{float(2 * relative[1, 1] + 10)}\n"
                f"b,10,12,{float(2 * relative[10, 12] + 10)}\n"
                f"c,18,22,{float(2 * relative[18, 22] + 10)}\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_DIR / "main.py"),
                    "--geotiff",
                    str(geotiff),
                    "--depth",
                    str(depth_path),
                    "--gcps",
                    str(gcps_path),
                    "--calibration",
                    "linear",
                    "--output-dir",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for name in ("absolute_dsm.npy", "absolute_dsm.tif", "preview_dsm.png", "metrics.json", "metadata.json"):
                self.assertTrue((output / name).is_file(), name)
            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["calibration_source"], "GCP")
            self.assertAlmostEqual(metadata["selected_calibration"]["coefficients"]["a"], 2.0, places=4)

    def test_cli_with_srtm_alignment_and_fusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            geotiff = root / "scene.tif"
            srtm = root / "srtm.tif"
            depth_path = root / "depth.npy"
            output = root / "output"
            height, width = 18, 22
            relative = np.linspace(1.0, 4.0, height * width, dtype=np.float32).reshape(height, width)
            elevation = 12.0 * relative + 75.0
            transform = from_origin(77.0, 29.0, 0.001, 0.001)
            with rasterio.open(
                geotiff,
                "w",
                driver="GTiff",
                width=width,
                height=height,
                count=3,
                dtype="uint8",
                crs="EPSG:4326",
                transform=transform,
            ) as dataset:
                dataset.write(np.full((3, height, width), 100, dtype=np.uint8))
            with rasterio.open(
                srtm,
                "w",
                driver="GTiff",
                width=width,
                height=height,
                count=1,
                dtype="float32",
                crs="EPSG:4326",
                transform=transform,
                nodata=-9999,
            ) as dataset:
                dataset.write(elevation, 1)
            np.save(depth_path, relative, allow_pickle=False)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_DIR / "main.py"),
                    "--geotiff",
                    str(geotiff),
                    "--depth",
                    str(depth_path),
                    "--srtm",
                    str(srtm),
                    "--calibration",
                    "linear",
                    "--output-dir",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = np.load(output / "absolute_dsm.npy", allow_pickle=False)
            self.assertEqual(result.shape, relative.shape)
            self.assertLess(float(np.nanmean(np.abs(result - elevation))), 0.1)
            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(metadata["is_absolute_elevation"])
            self.assertEqual(metadata["elevation_units"], "metres")


if __name__ == "__main__":
    unittest.main()
