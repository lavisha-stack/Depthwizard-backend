# DepthWizard Person 3 — calibration and geospatial fusion

This Python module converts a georeferenced RGB scene plus a monocular depth map
into an **estimated/fused absolute DSM**. It can use surveyed ground-control
points (GCPs), a local SRTM raster, or both. It preserves the RGB GeoTIFF's CRS
and exact footprint. For very large scenes it can work on the bounded monocular
depth grid, using a mathematically scaled affine transform rather than expanding
the prediction back into a multi-gigabyte source array.

The result is a hackathon-scale estimate, not survey-grade elevation. SRTM is a
coarse reference and monocular detail can be wrong.

## Project structure

```text
depthwizard_person3/
├── main.py                    # complete command-line pipeline
├── config.py                  # visible defaults
├── requirements.txt
├── src/
│   ├── io_utils.py            # GeoTIFF, depth, and metadata loading
│   ├── srtm.py                # local SRTM reading and tile-name helper
│   ├── alignment.py           # CRS-aware raster reprojection
│   ├── calibration.py         # GCP/SRTM pairs and candidate mappings
│   ├── fusion.py              # coarse baseline + fine detail
│   ├── validation.py          # MAE, RMSE, correlation, and bias
│   └── export.py              # GeoTIFF, PNG, and JSON writers
├── tests/
├── examples/
└── outputs/
```

## DEM, DTM, DSM, and nDSM

- **DEM** is a general term for a raster of elevation values.
- **DTM** usually means bare-earth terrain after vegetation and structures have
  been removed.
- **DSM** describes the visible top surface, which can include trees and roofs.
- **nDSM** expresses height above ground: `nDSM = DSM - reliable ground DTM`.

This module produces a DSM estimate. It does not have enough information to
promise a reliable DTM or exact building heights.

## What SRTM contributes

SRTM is elevation data derived from a radar mapping mission; it is **not an AI
model**. One-arc-second products are roughly 30 m resolution. Common products
use WGS84 horizontal coordinates and an EGM96-type orthometric vertical datum,
but the exact product documentation should always be checked.

SRTM helps anchor broad absolute elevation. It is too coarse to describe most
individual buildings, and it is not guaranteed to be a perfect bare-earth DTM.
Resampling it to small target pixels creates a matching grid, not new terrain
information.

## Relative monocular depth

A monocular model infers depth from one image. Its output may represent relative
depth, inverse depth, disparity-like values, normalized depth, or true metric
depth. A `.npy` array therefore is not automatically measured in metres. The
optional metadata JSON records the model's stated representation and whether
larger values mean near or far.

Depth must correspond pixel-for-pixel with either the source image or a known
bounded preprocessing grid. A shape mismatch stops the program by default.
`--use-depth-grid` derives a lower-resolution target with the same CRS, rotation,
and outer bounds; original-pixel GCPs are scaled to this working grid. The older
`--allow-depth-resampling` escape hatch expands depth to the target shape and
should be used only when that preprocessing relationship is explicitly known.

## Why geospatial alignment matters

A **CRS** defines how raster coordinates locate positions on Earth. An **affine
transform** converts pixel columns and rows into coordinates. Reprojection
converts between CRSs and samples values at the correct Earth locations.

`cv2.resize` only changes array dimensions. It does not understand CRS, bounds,
pixel origin, or ground resolution, so it is incorrect for aligning SRTM. This
module uses `rasterio.warp.reproject` and verifies exact output shape, CRS, and
transform. Bilinear resampling is the default for continuous elevation.

## Calibration

GCP CSV records can use either original source-image pixels:

```csv
name,row,col,elevation_m
gcp1,100,200,143.2
```

or geographic WGS84 coordinates:

```csv
name,longitude,latitude,elevation_m
gcp1,77.1025,28.6139,143.2
```

JSON may be a list of equivalent objects or an object containing a `gcps` list.
Longitude/latitude points are transformed from EPSG:4326 into the target CRS and
then converted to raster rows and columns. Out-of-bounds, non-finite, and missing
values are skipped with warnings.

Candidate mappings are:

- Linear: `H = aD + b`
- Inverse: `H = a(1/D) + b` (zero and invalid depths are excluded)
- Robust linear: Huber regression, which reduces the influence of outliers

`D` is model depth and `H` is elevation in metres. At least two distinct valid
samples are required for scale and offset. With 4–50 samples, candidate models
receive leave-one-out diagnostics. Larger SRTM sample sets use a deterministic
holdout. Automatic selection uses diagnostic RMSE where available.

These global mappings are baselines, not physical guarantees. Perspective,
camera pose, different surface types, and the model's representation can all
make `H = aD + b` fail. Training residuals measure fit to the supplied controls,
not independent accuracy.

### No-GCP fallback

When GCPs are absent, depth is Gaussian-smoothed to approximately the effective
SRTM scale. Coarse depth values are paired with aligned SRTM elevations and a
global mapping is fitted. This is a heuristic absolute-scale anchor. It does not
force every fine depth pixel to equal SRTM and does not make SRTM high resolution.

## Fusion

After calibration puts depth variation into approximate metres:

```text
depth_smooth = coarse Gaussian smoothing of calibrated_depth
depth_detail = calibrated_depth - depth_smooth
final_dsm = smoothed_aligned_srtm + alpha * depth_detail
```

SRTM supplies low-frequency elevation and monocular depth supplies estimated
high-frequency structure. `--alpha` controls detail strength and defaults to
`1.0`. If only GCPs are supplied, the calibrated depth estimate is exported
without an SRTM baseline. Raw relative depth is never simply added to SRTM.

## Install and run

Use a Python environment compatible with Rasterio, then run:

```powershell
python -m pip install -r requirements.txt

python main.py `
  --geotiff data/scene.tif `
  --depth data/relative_depth.npy `
  --depth-metadata data/depth_metadata.json `
  --srtm data/srtm.tif `
  --gcps data/gcps.csv `
  --reference data/reference_dsm.tif `
  --output-dir outputs
```

SRTM-only coarse calibration is also supported:

```powershell
python main.py --geotiff data/scene.tif --depth data/relative_depth.npy `
  --srtm data/srtm.tif --output-dir outputs
```

Useful options are `--calibration auto|linear|inverse|robust_linear`,
`--alpha 1.0`, `--use-depth-grid` for bounded large-scene predictions, and
`--allow-depth-resampling` only for explicitly expected shape mismatches.

At least `--srtm` or `--gcps` is required. The module does not download SRTM.

## Identifying a local SRTM tile

Read the target bounds, convert them to longitude/latitude (`EPSG:4326`) with
`rasterio.warp.transform_bounds`, and identify every intersecting one-degree
cell. Conventional names use the south-west corner, such as `N28E077.hgt`.
Scenes crossing a whole-degree boundary require multiple tiles, normally
mosaicked before this workflow. `srtm_tile_names_for_wgs84_bounds` implements
the naming step after bounds have been converted to EPSG:4326.

## Outputs

- `absolute_dsm.tif`: one float32 band, working CRS/transform/size, metre units,
  nodata `-9999`, and lossless compression.
- `preview_dsm.png`: coloured visual preview with a metre-labelled colorbar; not
  a scientific data product.
- `metrics.json`: validation values, or a clear “not calculated” status when no
  independent reference was supplied.
- `metadata.json`: inputs, source and working dimensions, target transform and
  footprint, depth range, calibration source/candidates/coefficients, accepted
  GCPs, fusion settings, validation, and limitations.

## Validation metrics

An optional reference DSM is independently reprojected to the target grid.
Metrics use only finite overlapping pixels:

- **MAE** is the average absolute error in metres.
- **RMSE** penalizes large errors more strongly than MAE.
- **Pearson r** measures similar spatial variation, not absolute accuracy. A high
  correlation can coexist with a large vertical bias.
- **Bias** is the mean `prediction - reference`; its sign shows over/underestimate.

## Important limitations

- **Urban:** SRTM cannot resolve individual roofs; monocular edges and roof
  shapes may be plausible but metrically wrong.
- **Hills:** perspective depth and terrain elevation are different physical
  quantities, so one global mapping may distort slopes.
- **Forests:** radar and monocular imagery can respond to different canopy levels.
- **Barren land:** weak visual texture can reduce monocular depth quality.
- **Vertical datums:** GCP, SRTM, and reference DSM heights may use different
  zero surfaces, creating systematic offsets.
- **Monocular ambiguity:** one image cannot uniquely determine metric geometry.
- **Coarse SRTM:** reprojection changes sampling, never native information content.

Run the offline synthetic tests with:

```powershell
python -m unittest discover -s tests -v
```
