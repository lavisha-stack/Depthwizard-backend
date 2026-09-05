"""Small, visible defaults for the first DepthWizard milestone."""

# Bilinear interpolation is appropriate for continuous elevation values.
DEFAULT_SRTM_RESAMPLING = "bilinear"

# A NaN is useful while processing because it cannot be mistaken for elevation.
ALIGNED_SRTM_NODATA = float("nan")

DEFAULT_ALPHA = 1.0
DEFAULT_OUTPUT_NODATA = -9999.0
MAX_CALIBRATION_SAMPLES = 200_000
