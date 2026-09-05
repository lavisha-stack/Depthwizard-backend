# DepthWizard integrated application

This was the project selected for the September 2026 Hackathon.

DepthWizard converts a PNG, JPEG, or GeoTIFF into relative or calibrated elevation and displays it as interactive 3D terrain.

Large imagery is decoded to a bounded 3072-pixel working grid and processed as overlapping model tiles. This avoids the old failure mode where a 16k aerial scene was reduced to one 518-pixel model pass and then falsely enlarged. Edge-connected black film/scanner borders are masked out of both inference statistics and 3D mesh geometry.

## Run

The simplest Windows start command is:

```powershell
.\start_depthwizard.cmd
```

This `.cmd` launcher works even when the machine's PowerShell execution policy
blocks `.ps1` files. It opens separate backend and frontend terminals, waits
until both HTTP services are genuinely ready, and then opens the site in the
high-performance GPU browser. The service terminals stay open if startup fails
so the underlying error remains visible.

To run the services separately without changing the execution policy, use
`.\start_backend.cmd`, `.\start_frontend.cmd`, and `.\open_gpu_viewer.cmd`.

Open two PowerShell terminals at this repository root:

```powershell
.\start_backend.ps1
```

```powershell
.\start_frontend.ps1
```

Then open `http://127.0.0.1:5173`. The normal uncalibrated path produces relative elevation. To produce elevations in metres, upload a genuinely georeferenced GeoTIFF together with GCP data, an SRTM/elevation raster, or both. SRTM `.hgt` uploads must keep their geographic tile name, such as `N28E077.hgt`.

On this workstation the backend environment has the official PyTorch CUDA 13.0
build and automatically selects the RTX 5060. If the environment is ever
recreated and startup reports CPU, run `./enable_cuda.ps1` once. The results
metadata shows `ML compute: CUDA`; the 3D viewport also displays the WebGL GPU
renderer in its lower-right corner.

On hybrid-GPU laptops, an embedded browser can ignore WebGL's
`powerPreference: high-performance` hint and remain on Intel graphics. With the
frontend already running, use `./open_gpu_viewer.ps1` to launch an isolated
Brave/Chrome session with Chromium's `--force_high_performance_gpu` preference.
The lower-right badge must say NVIDIA/RTX; if it says `INTEGRATED GPU · Intel`,
that browser process is still not using the discrete renderer.

The integrated flow is Person 4 (React) → Person 5 (FastAPI) → Persons 1–3 (image/depth/elevation pipeline) → Person 6 (Three.js viewer). The browser always receives a bounded `heightmap.json`; full-resolution NPY/GeoTIFF products remain downloadable.

Rendering uses the bounded 3072-pixel RGB texture, a 512-sample anti-aliased
terrain grid, GPU anisotropic texture filtering, soft self-shadowing, robust
relative-height clipping, and display-only surface smoothing. Numerical point
readings remain sampled from the unmodified elevation/depth field.

The 3D viewer opens in an orbiting Overview. Aim the centre reticle at the surface to read its elevation/relative height, slope, source row/column, calibration source, and map coordinate when a valid transform exists. Select Fly for keyboard navigation: `W`/`S` move along the camera heading, `A`/`D` strafe, `Q` or `Space` rises, and `E` or `Shift` descends. The toolbar includes movement-speed, mouse-look, and vertical-relief controls. PNG/JPEG and uncalibrated inputs are labelled `rel`; only a successfully calibrated GeoTIFF reports metres.

A `.tif` extension does not guarantee trustworthy georeferencing. DepthWizard validates the declared CRS against the raster's transformed centre and treats inconsistent metadata as non-georeferenced, with a visible warning. A generic monocular model estimates visual relative structure; it does not semantically guarantee that every road is ground or distinguish building height from canopy height. Operational DSM accuracy requires a remote-sensing height model and independent LiDAR/DEM/GCP validation.

## Absolute-elevation inputs

Open **Advanced calibration (optional)** before processing. Upload a correctly georeferenced optical GeoTIFF plus either:

- an overlapping SRTM/elevation GeoTIFF, or a correctly named SRTM HGT tile such as `N28E077.hgt`;
- a GCP CSV/JSON using original source pixels (`name,row,col,elevation_m`) or WGS84 coordinates (`name,longitude,latitude,elevation_m`);
- both, so SRTM supplies the broad terrain baseline while GCPs anchor the monocular scale and offset.

Example GCP files are in `depthwizard_person3/examples`. Without one of these references, the output intentionally remains relative and the UI states that absolute elevation is unavailable.

## Verify

```powershell
.\test_all.ps1
```

This runs all four Python suites, the 3D data/geometry tests, and the production frontend build.
