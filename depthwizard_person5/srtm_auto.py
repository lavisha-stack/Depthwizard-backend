"""Automatic SRTM reference acquisition for georeferenced DepthWizard inputs."""

from __future__ import annotations

import gzip
import logging
import math
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.merge import merge

logger = logging.getLogger("depthwizard")

# Public, no-account-required SRTM 30 m tiles. The bucket is documented by the
# AWS Open Data Registry and exposes conventional HGT tiles for elevation use.
_SRTM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/{ns}{lat:02d}/{tile}.hgt.gz"
_MIN_TILE_BYTES = 1_000_000


def _tile_name(latitude: int, longitude: int) -> str:
    ns = "N" if latitude >= 0 else "S"
    ew = "E" if longitude >= 0 else "W"
    return f"{ns}{abs(latitude):02d}{ew}{abs(longitude):03d}"


def _tile_names(bounds: tuple[float, float, float, float]) -> list[str]:
    left, bottom, right, top = bounds
    left -= 1e-7
    bottom -= 1e-7
    right += 1e-7
    top += 1e-7
    min_lon = math.floor(left)
    max_lon = math.ceil(right) - 1
    min_lat = math.floor(bottom)
    max_lat = math.ceil(top) - 1
    if min_lon > max_lon or min_lat > max_lat:
        raise ValueError("The georeferenced image has an invalid geographic extent.")
    if min_lat < -60 or max_lat > 59:
        raise ValueError("Automatic SRTM coverage is unavailable outside approximately 60°S–60°N.")
    return [_tile_name(lat, lon) for lat in range(min_lat, max_lat + 1) for lon in range(min_lon, max_lon + 1)]


def _download_tile(tile: str, cache_dir: Path) -> Path:
    target = cache_dir / f"{tile}.hgt"
    if target.is_file() and target.stat().st_size >= _MIN_TILE_BYTES:
        return target

    compressed = cache_dir / f"{tile}.hgt.gz"
    ns = tile[0]
    lat = int(tile[1:3])
    url = _SRTM_URL.format(ns=ns, lat=lat, tile=tile)
    logger.info("[SRTM] Downloading %s", url)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "DepthWizard/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response, compressed.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        compressed.unlink(missing_ok=True)
        raise RuntimeError(f"Could not download SRTM tile {tile}: {exc}") from exc

    try:
        with gzip.open(compressed, "rb") as source, target.open("wb") as destination:
            shutil.copyfileobj(source, destination)
    except (OSError, EOFError) as exc:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded SRTM tile {tile} is invalid: {exc}") from exc
    finally:
        compressed.unlink(missing_ok=True)

    if target.stat().st_size < _MIN_TILE_BYTES:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"SRTM tile {tile} was unexpectedly small.")
    return target


def ensure_srtm_reference(geotiff_path: Path, metadata: dict, cache_dir: Path) -> Path:
    """Download/cache SRTM tiles covering a GeoTIFF and return one mosaic path."""
    if not metadata.get("is_georeferenced"):
        raise ValueError("SRTM acquisition requires a georeferenced input.")
    crs = metadata.get("crs")
    transform_values = metadata.get("transform")
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    if not crs or not transform_values or width < 2 or height < 2:
        raise ValueError("The input is marked georeferenced but its CRS/grid metadata is incomplete.")

    transform = Affine(*transform_values)
    corners = [transform * (0, 0), transform * (width, 0), transform * (0, height), transform * (width, height)]
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    geographic = [transformer.transform(x, y) for x, y in corners]
    left = min(point[0] for point in geographic)
    right = max(point[0] for point in geographic)
    bottom = min(point[1] for point in geographic)
    top = max(point[1] for point in geographic)
    tiles = _tile_names((left, bottom, right, top))

    cache_dir.mkdir(parents=True, exist_ok=True)
    mosaic_path = cache_dir / ("srtm_" + "_".join(tiles) + ".tif")
    if mosaic_path.is_file() and mosaic_path.stat().st_size > 1024:
        logger.info("[SRTM] Reusing cached mosaic %s", mosaic_path)
        return mosaic_path

    tile_paths = [_download_tile(tile, cache_dir) for tile in tiles]
    try:
        sources = [rasterio.open(path) for path in tile_paths]
        try:
            mosaic, out_transform = merge(sources, nodata=-32768.0)
            profile = sources[0].profile.copy()
        finally:
            for source in sources:
                source.close()
    except Exception as exc:
        raise RuntimeError(f"Could not assemble the SRTM reference mosaic: {exc}") from exc

    profile.update(
        driver="GTiff",
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        transform=out_transform,
        crs="EPSG:4326",
        count=1,
        dtype="float32",
        nodata=-32768.0,
        compress="deflate",
    )
    with rasterio.open(mosaic_path, "w", **profile) as destination:
        destination.write(mosaic[:1].astype("float32", copy=False))

    return mosaic_path
