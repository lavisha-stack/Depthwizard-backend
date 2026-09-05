"""Fit relative-depth values to metric elevations using GCP or SRTM pairs."""

from __future__ import annotations

import csv
import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from pyproj import Transformer
from rasterio.transform import rowcol
from scipy.ndimage import gaussian_filter
from sklearn.linear_model import HuberRegressor


@dataclass
class CalibrationResult:
    model_type: str
    slope: float
    intercept: float
    sample_count: int
    diagnostics: dict[str, float | int | str | None]
    warnings: list[str] = field(default_factory=list)

    def predict(self, depth: np.ndarray) -> np.ndarray:
        values = np.asarray(depth, dtype=np.float32)
        if self.model_type == "inverse":
            with np.errstate(divide="ignore", invalid="ignore"):
                output = self.slope / values + self.intercept
        else:
            output = self.slope * values + self.intercept
        output = np.asarray(output, dtype=np.float32)
        output[~np.isfinite(values)] = np.nan
        return output


def load_gcps(path: str | Path) -> list[dict[str, Any]]:
    gcp_path = Path(path)
    if not gcp_path.is_file():
        raise FileNotFoundError(f"GCP file was not found: {gcp_path}")
    try:
        if gcp_path.suffix.lower() == ".csv":
            with gcp_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = [dict(row) for row in csv.DictReader(handle)]
        elif gcp_path.suffix.lower() == ".json":
            value = json.loads(gcp_path.read_text(encoding="utf-8"))
            rows = value.get("gcps") if isinstance(value, dict) else value
        else:
            raise ValueError("GCP input must be CSV or JSON.")
    except (OSError, json.JSONDecodeError, csv.Error) as exc:
        raise ValueError(f"Could not read GCP input: {exc}") from exc
    if not isinstance(rows, list) or not rows or not all(isinstance(item, dict) for item in rows):
        raise ValueError("GCP input must contain at least one control-point object/row.")
    return rows


def _number(record: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            try:
                result = float(value)
            except (TypeError, ValueError):
                return None
            return result if np.isfinite(result) else None
    return None


def extract_gcp_pairs(gcps, depth: np.ndarray, target_crs, transform, source_shape=None):
    depth_values: list[float] = []
    elevations: list[float] = []
    accepted: list[dict[str, Any]] = []
    lonlat_transformer = Transformer.from_crs("EPSG:4326", target_crs, always_xy=True)
    for index, record in enumerate(gcps, start=1):
        elevation = _number(record, "elevation_m", "elevation", "height_m", "height", "z")
        row = _number(record, "row", "pixel_row", "y_pixel")
        col = _number(record, "col", "column", "pixel_col", "x_pixel")
        coordinate_source = "pixel"
        if row is None or col is None:
            longitude = _number(record, "longitude", "lon", "lng")
            latitude = _number(record, "latitude", "lat")
            if longitude is not None and latitude is not None:
                x, y = lonlat_transformer.transform(longitude, latitude)
                row, col = rowcol(transform, x, y)
                coordinate_source = "longitude_latitude"
        if elevation is None or row is None or col is None:
            warnings.warn(f"Skipping GCP {index}: missing/invalid coordinates or elevation.", stacklevel=2)
            continue
        source_row, source_col = float(row), float(col)
        # Pixel GCPs are documented in original source-image coordinates. When
        # calibration uses a bounded working grid, map them to that grid while
        # longitude/latitude GCPs already use its scaled affine transform.
        if coordinate_source == "pixel" and source_shape is not None:
            source_height, source_width = source_shape
            row = source_row * (depth.shape[0] - 1) / max(source_height - 1, 1)
            col = source_col * (depth.shape[1] - 1) / max(source_width - 1, 1)
            coordinate_source = "source_pixel"
        pixel_row, pixel_col = int(round(row)), int(round(col))
        if not (0 <= pixel_row < depth.shape[0] and 0 <= pixel_col < depth.shape[1]):
            warnings.warn(f"Skipping GCP {index}: point is outside the image.", stacklevel=2)
            continue
        sample = float(depth[pixel_row, pixel_col])
        if not np.isfinite(sample):
            warnings.warn(f"Skipping GCP {index}: depth is invalid at the point.", stacklevel=2)
            continue
        depth_values.append(sample)
        elevations.append(elevation)
        accepted.append(
            {
                "name": str(record.get("name") or record.get("id") or f"gcp_{index}"),
                "row": pixel_row,
                "col": pixel_col,
                "relative_depth": sample,
                "elevation_m": elevation,
                "coordinate_source": coordinate_source,
                "source_row": source_row if coordinate_source == "source_pixel" else None,
                "source_col": source_col if coordinate_source == "source_pixel" else None,
            }
        )
    return np.asarray(depth_values), np.asarray(elevations), accepted


def _nan_gaussian(values: np.ndarray, sigma: float) -> np.ndarray:
    valid = np.isfinite(values)
    filled = np.where(valid, values, 0.0).astype(np.float32)
    weights = gaussian_filter(valid.astype(np.float32), sigma=sigma, mode="nearest")
    blurred = gaussian_filter(filled, sigma=sigma, mode="nearest")
    result = np.full(values.shape, np.nan, dtype=np.float32)
    usable = weights > 1e-6
    result[usable] = blurred[usable] / weights[usable]
    return result


def coarse_srtm_pairs(
    depth: np.ndarray, aligned_srtm: np.ndarray, sigma_pixels: float, max_samples: int
):
    if aligned_srtm is None:
        raise ValueError("SRTM data is required for SRTM-only calibration.")
    smoothed_depth = _nan_gaussian(depth, max(float(sigma_pixels), 0.01))
    valid = np.isfinite(smoothed_depth) & np.isfinite(aligned_srtm)
    flat_indices = np.flatnonzero(valid)
    if flat_indices.size < 2:
        raise ValueError("Fewer than 2 overlapping SRTM/depth samples are available.")
    if flat_indices.size > max_samples:
        positions = np.linspace(0, flat_indices.size - 1, max_samples, dtype=np.int64)
        flat_indices = flat_indices[positions]
    return (
        smoothed_depth.ravel()[flat_indices].astype(np.float64),
        aligned_srtm.ravel()[flat_indices].astype(np.float64),
        flat_indices,
    )


def _feature(depth: np.ndarray, model_type: str) -> tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(depth)
    if model_type == "inverse":
        valid &= np.abs(depth) > 1e-12
        return 1.0 / depth[valid], valid
    return depth[valid], valid


def _fit_coefficients(x: np.ndarray, y: np.ndarray, model_type: str) -> tuple[float, float]:
    if x.size < 2 or np.ptp(x) <= 1e-12:
        raise ValueError(f"{model_type} calibration needs at least two distinct depth samples.")
    if model_type == "robust_linear":
        estimator = HuberRegressor().fit(x.reshape(-1, 1), y)
        return float(estimator.coef_[0]), float(estimator.intercept_)
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def _metrics(prediction: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    residual = prediction - truth
    correlation = float(np.corrcoef(prediction, truth)[0, 1]) if truth.size > 1 and np.std(prediction) > 0 and np.std(truth) > 0 else 0.0
    return {
        "mae": float(np.mean(np.abs(residual))),
        "rmse": float(np.sqrt(np.mean(residual * residual))),
        "bias": float(np.mean(residual)),
        "correlation": correlation,
    }


def _cross_validated_rmse(x: np.ndarray, y: np.ndarray, model_type: str) -> tuple[float, str]:
    count = x.size
    if count < 4:
        return float("nan"), "not_available_fewer_than_4_samples"
    if count <= 50:
        predictions = np.empty(count, dtype=np.float64)
        for index in range(count):
            keep = np.arange(count) != index
            slope, intercept = _fit_coefficients(x[keep], y[keep], model_type)
            predictions[index] = slope * x[index] + intercept
        return float(np.sqrt(np.mean((predictions - y) ** 2))), "leave_one_out"
    validation_indices = np.arange(4, count, 5)
    training = np.ones(count, dtype=bool)
    training[validation_indices] = False
    slope, intercept = _fit_coefficients(x[training], y[training], model_type)
    prediction = slope * x[validation_indices] + intercept
    return float(np.sqrt(np.mean((prediction - y[validation_indices]) ** 2))), "deterministic_holdout"


def _fit_candidate(depth: np.ndarray, height: np.ndarray, model_type: str) -> CalibrationResult:
    feature, valid_depth = _feature(depth, model_type)
    valid_height = np.isfinite(height)
    combined = valid_depth & valid_height
    x = (1.0 / depth[combined]) if model_type == "inverse" else depth[combined]
    y = height[combined]
    slope, intercept = _fit_coefficients(x, y, model_type)
    training = _metrics(slope * x + intercept, y)
    validation_rmse, validation_method = _cross_validated_rmse(x, y, model_type)
    diagnostics: dict[str, float | int | str | None] = {
        **training,
        "validation_rmse": validation_rmse if np.isfinite(validation_rmse) else None,
        "validation_method": validation_method,
    }
    notes: list[str] = []
    if x.size < 4:
        notes.append("Fewer than 4 controls: calibration cannot be independently cross-validated.")
    return CalibrationResult(model_type, slope, intercept, int(x.size), diagnostics, notes)


def fit_candidate_models(
    depth: np.ndarray, height: np.ndarray, requested: str = "auto"
) -> tuple[CalibrationResult, list[CalibrationResult]]:
    depth = np.asarray(depth, dtype=np.float64).ravel()
    height = np.asarray(height, dtype=np.float64).ravel()
    if depth.shape != height.shape:
        raise ValueError("Depth/elevation calibration arrays must have the same shape.")
    candidates: list[CalibrationResult] = []
    errors: list[str] = []
    for model_type in ("linear", "inverse", "robust_linear"):
        try:
            candidates.append(_fit_candidate(depth, height, model_type))
        except (ValueError, RuntimeError) as exc:
            errors.append(f"{model_type}: {exc}")
    if not candidates:
        raise ValueError("No calibration model could be fitted. " + "; ".join(errors))
    if requested != "auto":
        selected = next((item for item in candidates if item.model_type == requested), None)
        if selected is None:
            raise ValueError(f"Requested {requested} calibration could not be fitted. " + "; ".join(errors))
        return selected, candidates

    def score(item: CalibrationResult) -> float:
        value = item.diagnostics.get("validation_rmse")
        return float(value) if value is not None else float(item.diagnostics["rmse"])

    return min(candidates, key=score), candidates
