"""Coordinate conversion helpers for georeferenced imagery."""

from __future__ import annotations

from affine import Affine
from pyproj import CRS, Transformer
from rasterio.transform import xy


def pixel_to_map(row: float, col: float, transform: Affine) -> tuple[float, float]:
    """Convert a pixel centre to map x, y coordinates.

    row is the vertical pixel coordinate and col is the horizontal coordinate.
    """
    x, y = xy(transform, row, col, offset="center")
    return float(x), float(y)


def map_to_pixel(x: float, y: float, transform: Affine) -> tuple[float, float]:
    """Convert map x, y to fractional centre-based row, col coordinates.

    Integer row/column values refer to pixel centres, matching pixel_to_map.
    Keeping fractional results avoids throwing away sub-pixel precision.
    """
    col_corner, row_corner = (~transform) @ (x, y)
    return float(row_corner - 0.5), float(col_corner - 0.5)


def to_lonlat(x: float, y: float, source_crs: str | CRS) -> tuple[float, float]:
    """Convert image-CRS coordinates to longitude, latitude (EPSG:4326)."""
    transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    longitude, latitude = transformer.transform(x, y)
    return float(longitude), float(latitude)


def pixel_to_lonlat(
    row: float, col: float, transform: Affine, source_crs: str | CRS
) -> tuple[float, float]:
    """Convenience conversion from an image pixel centre to lon/lat."""
    x, y = pixel_to_map(row, col, transform)
    return to_lonlat(x, y, source_crs)
