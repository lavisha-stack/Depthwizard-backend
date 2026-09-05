# DepthWizard – Person 1

This hackathon module accepts an aerial/remote-sensing TIFF, PNG, or JPEG,
records its original pixel grid, validates GeoTIFF metadata, and makes a
bounded model-ready RGB image. It does **not** estimate depth or build a DSM.

## What it handles

- `.tif` and `.tiff`, including georeferenced and ordinary TIFFs
- `.png`, `.jpg`, and `.jpeg` as explicitly non-georeferenced images
- Rasterio's band-first arrays (`bands × rows × columns`), converted to
  `rows × columns × 3`
- `uint8`, `uint16`, floating-point, and other numeric raster types
- nodata masks and non-finite values
- pixel/map coordinate conversion and optional EPSG:4326 longitude/latitude

For rasters with more than three bands, bands 1–3 are used. One-band images are
repeated into three channels; for two-band images, band 2 is repeated as channel
3. These fallbacks provide an RGB-shaped array but do not claim false-colour data
is natural-colour RGB.

## Installation

Python 3.10 or newer is recommended.

```bash
cd depthwizard_person1
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py --input path/to/scene.tif --output person1_output --max-model-size 3072
```

The command prints dimensions, band count, georeferencing status, CRS, pixel
resolution (when available), and the output location. Invalid paths and unreadable
images produce a short `Error:` message and a non-zero exit code.

## Output files

| File | Purpose |
| --- | --- |
| `rgb_original.npy` | Original selected RGB pixels and original numeric dtype; no resize/flip/crop |
| `rgb_model.png` | uint8 RGB input for the depth model, bounded when requested and in the original orientation |
| `valid_mask.npy` | Boolean `height × width` mask; `True` means valid data |
| `metadata.json` | Dimensions, input type, dtype, CRS, transform, bounds, pixel size, nodata, and grid mapping |
| `preview.png` | Smaller inspection-only preview; never use it for pixel-aligned depth |

Normalization uses the 2nd and 98th percentiles independently per channel,
considering only valid finite pixels. It creates a new uint8 image and never
modifies `rgb_original.npy`. Invalid model pixels are black and remain identified
by `valid_mask.npy`.

`--max-model-size` performs bounded decode directly through Rasterio/Pillow,
avoiding multi-gigabyte arrays for large compressed rasters. Metadata separately
records original and model dimensions plus their scale. TIFFs with no declared
nodata are checked for edge-connected near-black scanner/film borders; inferred
border pixels remain false in `valid_mask.npy`.

The module does not trust a CRS tag blindly. It transforms the raster centre to
longitude/latitude and checks the declared CRS area of use. Inconsistent tags
are retained as `declared_crs`, reported in `georeference_warning`, and excluded
from metric calibration fields.

## Team hand-off

Send **Person 2**:

- `rgb_model.png` (the normal input to monocular depth estimation)
- optionally `rgb_original.npy` if their loader accepts NumPy arrays

Person 2 does not need geospatial metadata and must return depth in the same
orientation. If their model internally resizes, they should resize its depth map
back to `metadata.json`'s `width × height`.

Send **Person 3**:

- `metadata.json`
- `valid_mask.npy`
- the depth map returned by Person 2
- optionally `rgb_original.npy` for colour/reference output

The six transform values in JSON are `(a, b, c, d, e, f)` and can be rebuilt
with `Affine(*metadata["transform"])`. A CRS and transform are `null` for PNG,
JPEG, and non-georeferenced TIFF inputs; the module never invents either.

## Coordinate helpers

```python
from affine import Affine
from src.coordinates import map_to_pixel, pixel_to_map, to_lonlat

transform = Affine(*metadata["transform"])
x, y = pixel_to_map(row=100, col=250, transform=transform)
row, col = map_to_pixel(x, y, transform)
longitude, latitude = to_lonlat(x, y, metadata["crs"])
```

`row` is vertical (top to bottom); `col` is horizontal (left to right).
Conversions use pixel centres, so an integer pixel converts to map coordinates
and back to approximately that same integer row and column.

## File guide

- `main.py` – command-line workflow and readable summary/errors
- `config.py` – accepted extensions and normalization/preview settings
- `src/image_loader.py` – input detection plus Pillow loading
- `src/geotiff.py` – Rasterio loading, band layout, masks, and metadata
- `src/preprocessing.py` – floating-point-safe uint8 normalization
- `src/coordinates.py` – pixel/map and map/lon-lat conversion
- `src/output.py` – writes the five hand-off artifacts
- `tests/test_pipeline.py` – synthetic PNG, TIFF, GeoTIFF, round-trip, and CLI checks

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests generate temporary images, including a nodata GeoTIFF, verify array
orientation, test pixel → map → pixel round-tripping, and exercise all CLI output
files. No external test data is needed.

## Scope

This module ends after image inspection, metadata extraction, RGB preparation,
and clean file output. Depth models, SRTM/GCP work, DSM fusion, rendering, and web
development belong to later modules.
