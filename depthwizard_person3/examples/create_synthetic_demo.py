"""Create a tiny, deterministic GeoTIFF + DEM + GCP DepthWizard demo set."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.transform import from_origin


ROOT = Path(__file__).resolve().parent
HEIGHT, WIDTH = 120, 160
TRANSFORM = from_origin(77.1000, 28.6500, 0.0001, 0.0001)


def write_raster(path: Path, values: np.ndarray, transform: Affine, dtype: str) -> None:
    count = 1 if values.ndim == 2 else values.shape[0]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=values.shape[-1],
        height=values.shape[-2],
        count=count,
        dtype=dtype,
        crs="EPSG:4326",
        transform=transform,
        compress="deflate",
    ) as dataset:
        dataset.write(values if values.ndim == 3 else values, None if values.ndim == 3 else 1)


def main() -> None:
    rows, cols = np.mgrid[:HEIGHT, :WIDTH]
    ground = 142.0 + cols * 0.025 + rows * 0.012
    surface = ground.copy()

    rgb = np.empty((3, HEIGHT, WIDTH), dtype=np.uint8)
    rgb[0] = np.clip(72 + cols * 0.16 + rows * 0.05, 0, 255)
    rgb[1] = np.clip(105 + cols * 0.08, 0, 255)
    rgb[2] = np.clip(66 + rows * 0.08, 0, 255)

    # Two orthogonal roads remain at ground level.
    road = (np.abs(cols - 78) <= 7) | (np.abs(rows - 62) <= 6)
    rgb[:, road] = np.array([[72], [75], [78]], dtype=np.uint8)

    buildings = [
        (15, 45, 16, 55, 9.0, (205, 190, 170)),
        (18, 52, 96, 132, 14.0, (190, 205, 215)),
        (76, 105, 17, 52, 7.0, (215, 195, 160)),
        (78, 108, 101, 145, 11.0, (180, 185, 195)),
    ]
    for r0, r1, c0, c1, height_m, colour in buildings:
        surface[r0:r1, c0:c1] += height_m
        rgb[:, r0:r1, c0:c1] = np.asarray(colour, dtype=np.uint8)[:, None, None]
        rgb[:, r0:r0 + 2, c0:c1] = 245
        rgb[:, r0:r1, c0:c0 + 2] = 235

    # Tree crowns are visible DSM surfaces, but deliberately lower/rounder than roofs.
    for centre_row, centre_col, radius, height_m in ((29, 72, 9, 5.0), (88, 83, 11, 6.0), (42, 145, 8, 4.5)):
        distance = np.hypot(rows - centre_row, cols - centre_col)
        crown = distance <= radius
        surface[crown] += height_m * np.sqrt(np.clip(1 - (distance[crown] / radius) ** 2, 0, 1))
        rgb[0, crown], rgb[1, crown], rgb[2, crown] = 38, 118, 48

    write_raster(ROOT / "demo_scene.tif", rgb, TRANSFORM, "uint8")
    write_raster(ROOT / "demo_reference_dsm.tif", surface.astype(np.float32), TRANSFORM, "float32")

    # Coarse ground-only DEM covering exactly the same footprint.
    factor = 4
    coarse = ground.reshape(HEIGHT // factor, factor, WIDTH // factor, factor).mean(axis=(1, 3))
    write_raster(
        ROOT / "demo_ground_dem.tif",
        coarse.astype(np.float32),
        TRANSFORM @ Affine.scale(factor, factor),
        "float32",
    )

    controls = [(62, 78), (30, 28), (30, 112), (90, 34), (92, 122), (29, 72)]
    with (ROOT / "demo_gcps.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("name", "row", "col", "elevation_m"))
        for index, (row, col) in enumerate(controls, start=1):
            writer.writerow((f"control_{index}", row, col, f"{surface[row, col]:.3f}"))

    print("Created demo_scene.tif, demo_ground_dem.tif, demo_reference_dsm.tif, and demo_gcps.csv")


if __name__ == "__main__":
    main()
