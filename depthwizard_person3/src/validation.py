"""Independent DSM validation metrics."""

from __future__ import annotations

import numpy as np


def calculate_metrics(prediction: np.ndarray, reference: np.ndarray) -> dict:
    if prediction.shape != reference.shape:
        raise ValueError("Prediction and reference DSM shapes do not match.")
    valid = np.isfinite(prediction) & np.isfinite(reference)
    count = int(valid.sum())
    if count == 0:
        raise ValueError("Prediction and reference DSM have no finite overlapping pixels.")
    predicted = prediction[valid].astype(np.float64)
    observed = reference[valid].astype(np.float64)
    residual = predicted - observed
    correlation = (
        float(np.corrcoef(predicted, observed)[0, 1])
        if count > 1 and np.std(predicted) > 0 and np.std(observed) > 0
        else None
    )
    return {
        "status": "calculated",
        "sample_count": count,
        "mae_m": float(np.mean(np.abs(residual))),
        "rmse_m": float(np.sqrt(np.mean(residual * residual))),
        "bias_m": float(np.mean(residual)),
        "pearson_r": correlation,
    }
