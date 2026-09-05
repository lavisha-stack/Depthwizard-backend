# Calibration input examples

The integrated upload form accepts one RGB GeoTIFF plus an optional local SRTM/DEM file and optional GCP file:

Run `python create_synthetic_demo.py` once to generate a tiny offline dataset:

```text
examples/
├── demo_scene.tif          # upload as the RGB source
├── demo_ground_dem.tif     # upload in the SRTM/elevation field
├── demo_gcps.csv           # upload in the GCP field
└── demo_reference_dsm.tif  # optional CLI-only validation reference
```

The artificial scene contains ground, two roads, four flat buildings, and three
rounded tree crowns with known elevations. It verifies file handling,
georeferencing, calibration, fusion, export, and rendering; it is not an accuracy
benchmark for a model trained on real aerial imagery.

Use `gcps_source_pixels.csv` when control points were measured against the original RGB image. Rows start at the top and columns at the left; both are zero-based. DepthWizard maps these coordinates to its bounded calibration grid automatically.

Use `gcps_wgs84.csv` for geographic controls. Longitude and latitude must be WGS84 (`EPSG:4326`), while `elevation_m` is the measured vertical value in metres. Keep every vertical source on a consistent datum when possible.

SRTM `.hgt` filenames must retain the conventional southwest-corner tile name because GDAL derives their location from it. Scenes crossing tile boundaries need a georeferenced mosaic supplied as a GeoTIFF.
