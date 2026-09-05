# DepthWizard — Person 6 Terrain Viewer

A Vite + Three.js module that turns a calibrated DSM or relative height map and aligned RGB image into an interactive terrain. It provides an orbiting overview, first-person navigation, point elevation inspection, visualization modes, and an automatic flythrough. With no URLs supplied it opens a deterministic procedural demo.

## Run

```bash
npm install
npm run dev
```

Production check: `npm run build`. The deployable output is `dist/`.

## Integration API

```js
import { createTerrainViewer } from './src/main.js';

const viewer = await createTerrainViewer({
  container: document.querySelector('#terrain'),
  apiBaseUrl: 'http://localhost:8000/results/job-123',
  // Explicit URLs override apiBaseUrl defaults:
  heightmapUrl: '/data/heightmap.json',
  textureUrl: '/data/texture.png',
  metadataUrl: '/data/metadata.json',
  verticalExaggeration: 1,
});

// Later: viewer.reset(); viewer.destroy();
```

The container must have a usable height (for example `height: 70vh`). `apiBaseUrl` resolves `heightmap.json` and `texture.png`. A missing texture gracefully falls back to elevation colors. A missing heightmap URL intentionally selects demo terrain; a failed supplied URL displays an error.

## Scene construction and orientation

The flattened array is row-major: `heights[row * width + col]`. Each sample becomes one vertex:

- **X = column**, centered around zero.
- **Y = (elevation − minimum elevation) × vertical scale × exaggeration**. Metric DSMs use a vertical scale of 1. Relative maps are display-normalized because they have no physical vertical scale.
- **Z = row**, centered around zero.
- `pixelSizeX` and `pixelSizeY` from metadata determine physical aspect ratio; both default to 1. Projected grid units are converted with `horizontal_unit_to_metre` when supplied. EPSG:4326/CRS84 degree spacing is converted to approximate local metres at the image-centre latitude, so geographic rasters are not rendered as physically microscopic terrain and metric slopes remain meaningful.

The convention is deterministic: DSM `[row, col]` corresponds to RGB image pixel `(col, row)`, and the top DSM row is the top texture row. Three.js's standard image-texture Y flip matches the UVs produced after rotating the plane into XZ. The RGB and DSM must already be co-registered and have the same geographic crop.

Relative model output receives one conservative display-only smoothing pass to reduce ringing and needle-like spikes. Point measurements always sample the unmodified height field. This distinction avoids improving visual quality by silently changing reported data.

Large DSMs are sampled to at most 512 vertices on their longest side in the browser (about 262k vertices maximum). Input reduction is bilinear rather than nearest-neighbour to prevent terracing. Invalid/nodata samples are filled only to support interpolation, while mesh triangles touching the invalid mask are removed; this prevents black scan borders from becoming vertical cliffs. An entirely invalid DSM gives a clear error.

Relative-depth geometry uses 1st/99th-percentile clipping, two conservative
display-only smoothing passes, and a default relief equal to 3% of scene width.
This suppresses isolated walls and ringing without changing the raw values shown
by the measurement HUD. The texture uses mipmapping and up to 16× anisotropic
filtering; soft terrain self-shadows and a narrower camera field of view improve
low-angle readability. The lower-right badge reports the WebGL renderer selected
by the browser.

## Heightmap format

```json
{"width":3,"height":2,"elevation_min":10,"elevation_max":15,"heights":[10,11,12,13,14,15],"valid":[true,true,true,true,true,true]}
```

Optional `metadata.json`:

```json
{"pixelSizeX":10,"pixelSizeY":10,"nodata":-9999,"crs":"EPSG:4326"}
```

JSON cannot represent NaN. Export invalid samples as `null` or a declared numeric `nodata` value.

## Convert a NumPy DSM

```bash
python tools/prepare_heightmap.py fused_dsm.npy public/heightmap.json --max-size 512
```

The tool requires only NumPy, fills NaNs from neighbouring terrain, preserves aspect ratio, uses NumPy bilinear resampling, and rounds values to keep JSON moderate. `--decimals` controls precision. Person 5 can run this after calibration and serve the output alongside the aligned PNG.

## Controls

The viewer starts in **Overview** mode: drag to orbit, right-drag to pan, and use the wheel to zoom. Select **Fly**, click inside the terrain to capture the mouse, and use the mouse to look. `W`/`S` move along the camera's horizontal heading, `A`/`D` strafe without rotating, `Q` or `Space` rises, and `E` or either `Shift` descends. Press Escape to release the mouse. The camera follows the displayed surface plus the chosen flight altitude and stays inside the DSM boundary. Movement speed and mouse sensitivity are adjustable from the toolbar.

The centre reticle is an analysis probe. Its HUD reports the aimed original-source pixel, its bilinearly sampled elevation/relative height, local slope, calibration source, and map coordinate when metadata includes an affine transform. Calibrated data is labelled in its metric units; uncalibrated data is labelled `rel`, explicitly says absolute elevation is unavailable, and marks its slope `visual` because a unitless vertical field cannot provide a physical slope.

The toolbar switches texture/elevation/wireframe modes, changes relief live, selects Overview or Fly, and starts, pauses, resumes, or resets the automatic flythrough. Relative results are limited to 0.2×–2× visual relief to prevent misleading spikes; metric DSMs allow 0.2×–5×. Renderer resolution is capped at 2× device pixel ratio and automatically follows container resizing.

## Person 3 to Person 6 contract

For a calibrated job, `metadata.json` should contain `is_absolute_elevation`,
`elevation_units`, `calibration_source`, and `target` with `crs`, six affine
coefficients in `transform`, working `width`/`height`, original
`source_width`/`source_height`, and `pixel_resolution`. Person 5 serves that file
as the viewer metadata URL. This lets the HUD map bounded mesh samples back to
original pixels and map coordinates without pretending relative depth is metric.
