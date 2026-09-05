"""Small configuration values for the Person 1 pipeline."""

from pathlib import Path


SUPPORTED_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}

# Robust percentile stretching keeps a few extreme pixels from making the
# complete model image look almost black or white.
LOW_PERCENTILE = 2.0
HIGH_PERCENTILE = 98.0

# preview.png is only for quick inspection. rgb_model.png is never resized.
PREVIEW_MAX_SIZE = (1200, 1200)


def validate_input_path(input_path: Path) -> None:
    """Raise a readable error when the input cannot be processed."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input image does not exist: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")
    if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        accepted = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported image type '{input_path.suffix}'. Expected: {accepted}")
