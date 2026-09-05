# DepthWizard Person 5 — Backend/API Integration

This module is the bridge between the website and the core image pipeline. It receives an image, creates an isolated job directory, runs the scripts supplied by Persons 1, 2, and 3 in order, and exposes their outputs to Person 4's frontend and Person 6's 3D viewer.

It does **not** implement depth estimation, geospatial calibration, DSM generation, or 3D rendering.

## Files

- `main.py` creates the FastAPI app, CORS configuration, and health endpoint.
- `config.py` contains environment-configurable paths, limits, filenames, and mock mode.
- `file_manager.py` safely saves uploads, creates jobs, stores status, and resolves result files.
- `pipeline_runner.py` contains the three subprocess adapters and strict stage ordering.
- `api/routes.py` implements upload, status, results, and file endpoints.
- `requirements.txt` lists only backend dependencies. The ML/geospatial dependencies remain owned by Persons 1-3 and must exist in the same Python environment if their scripts need them.

## Install and run

From this directory:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-pipeline.txt
uvicorn main:app --reload
```

Both install commands must run inside the same activated virtual environment.
The backend starts Persons 1-3 with `sys.executable`; installing only the web
requirements will make Person 1 fail on imports such as `affine`/`rasterio`.

Open `http://127.0.0.1:8000/docs` for interactive API documentation. The health check is `http://127.0.0.1:8000/health`.

For normal development, the workspace root also contains launchers that avoid
directory and package-runner mistakes. Run these in two separate PowerShell
terminals while your current directory is the workspace root:

```powershell
.\start_backend.ps1
.\start_frontend.ps1
```

The frontend launcher tries `pnpm`, then `npm`, then the Codex desktop bundled
`pnpm` path when available.

For an NVIDIA RTX 50-series workstation, run `..\enable_cuda.ps1` once after
creating the virtual environment. It installs the matching official CUDA 13.0
PyTorch wheels without changing the other pipeline dependencies. Backend
startup prints the selected ML device, and every job records `device: cuda` or
`device: cpu` in its metadata.

## Configure integration

Defaults assume the sibling directories `depthwizard_person1`, `depthwizard_person2`, and `depthwizard_person3`, each with `main.py`. Override any value with an environment variable:

```powershell
$env:PERSON1_SCRIPT = "C:\path\to\person1\main.py"
$env:PERSON2_SCRIPT = "C:\path\to\person2\main.py"
$env:PERSON3_SCRIPT = "C:\path\to\person3\main.py"
$env:PERSON1_RGB_FILENAME = "rgb_model.png"
$env:PERSON1_MASK_FILENAME = "valid_mask.npy"
$env:PERSON2_DEPTH_FILENAME = "relative_depth.npy"
$env:PERSON3_SRTM = "C:\data\srtm_tile.tif"  # or set PERSON3_GCPS
$env:PERSON3_GCPS = "C:\data\control_points.csv"
$env:MAX_UPLOAD_SIZE_MB = "500"
$env:MODEL_MAX_SIZE = "3072"               # bounded long edge before tiled inference
$env:VIEWER_GRID_SIZE = "512"              # browser terrain samples on the long edge
$env:DEPTH_MODEL = "depth_anything_v2_base"  # default; use small for slower CPU-only computers
uvicorn main:app --reload
```

The default image limit is 500 MB. Uploads are copied in 1 MB chunks, so the
backend does not read the entire HTTP upload into RAM at once. Processing is a
different matter: a compressed 500 MB GeoTIFF can expand to several gigabytes
of RGB, mask, depth, and DSM arrays. Large scenes therefore require sufficient
RAM, disk space, and processing time even though the upload itself is accepted.

The adapter command lines are deliberately centralized in `pipeline_runner.py`. Their defaults match the current sibling modules (`--input/--output` for Persons 1-2 and `--geotiff/--depth/--output-dir` for Person 3). The current Person 3 script requires SRTM, GCPs, or both, so configure `PERSON3_SRTM` and/or `PERSON3_GCPS` for a real run. Large scenes automatically pass `--use-depth-grid`, preserving the GeoTIFF footprint and CRS at the bounded Person 2 resolution instead of expanding depth back to the original multi-gigabyte grid. Absolute calibration is rejected when Person 1 reports missing or geographically inconsistent georeferencing. Update only `run_person1`, `run_person2`, and `run_person3` if teammates change those CLI flags. Commands use `sys.executable`, argument lists, captured output, and never `shell=True`. A failed stage stops the later stages.

## Mock/testing mode

Mock mode creates small placeholder outputs so the frontend can be developed before Persons 1-3 are ready:

```powershell
$env:MOCK_PIPELINE = "true"
uvicorn main:app --reload
```

Mock mode is off by default. Do not set `MOCK_PIPELINE=true` for the final demonstration.

Run the lightweight API contract tests with:

```powershell
python -m unittest discover -s tests -v
```

## API

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Server health |
| POST | `/api/process` | Upload one image and queue its processing job |
| GET | `/api/status/{job_id}` | Read job status |
| GET | `/api/results/{job_id}` | Read metadata and output URLs |
| GET | `/api/files/{job_id}/{filename}` | Download/display a generated file |

The upload endpoint saves and validates the files, queues processing as a FastAPI background task, and immediately returns the job ID. The frontend polls the status endpoint while Persons 1–3 run, so a large model job does not keep one HTTP request open until completion. This single-process queue is suitable for the hackathon deployment; a production multi-machine deployment should move jobs to a durable worker queue.

### Person 4: exact browser call

The multipart field name is `image`. Optional calibration uploads use `srtm`
(`.tif`, `.tiff`, or `.hgt`) and `gcp` (`.csv` or `.json`):

```javascript
const form = new FormData();
form.append("image", file);
if (srtmFile) form.append("srtm", srtmFile);
if (gcpFile) form.append("gcp", gcpFile);

const response = await fetch("http://127.0.0.1:8000/api/process", {
  method: "POST",
  body: form,
});
const body = await response.json();
if (!response.ok) throw new Error(JSON.stringify(body.detail));

const status = await fetch(`http://127.0.0.1:8000/api/status/${body.job_id}`)
  .then((r) => r.json());
const results = await fetch(`http://127.0.0.1:8000/api/results/${body.job_id}`)
  .then((r) => r.json());

document.querySelector("#depth-preview").src = results.depth_preview_url;
```

The upload response is immediate:

```json
{"job_id": "job_7f82a91c1234", "status": "queued", "progress": 5}
```

After the status becomes `completed`, the results response contains fields such as:

```json
{
  "job_id": "job_7f82a91c1234",
  "status": "completed",
  "input_type": "geotiff",
  "is_georeferenced": true,
  "depth_preview_url": "http://127.0.0.1:8000/api/files/job_7f82a91c1234/relative_depth_preview.png",
  "dsm_preview_url": "http://127.0.0.1:8000/api/files/job_7f82a91c1234/dsm_preview.png",
  "dsm_download_url": "http://127.0.0.1:8000/api/files/job_7f82a91c1234/fused_dsm.npy",
  "three_d_data_url": "http://127.0.0.1:8000/api/files/job_7f82a91c1234/heightmap.json",
  "heightmap_url": "http://127.0.0.1:8000/api/files/job_7f82a91c1234/heightmap.json",
  "texture_url": "http://127.0.0.1:8000/api/files/job_7f82a91c1234/rgb_model.png"
}
```

Only metadata actually read from Person 1-3 JSON files is included; the backend does not invent geospatial values.

### Person 6: exact data contract

Read `GET /api/results/{job_id}` and use:

- `heightmap_url` (also `three_d_data_url`) for browser-ready `heightmap.json`. Raw NPY/TIFF data is exposed separately through `dsm_download_url`.
- `texture_url` for the prepared RGB image.
- `width`, `height`, `minimum_elevation`, and `maximum_elevation` when Persons 1-3 included them in their metadata JSON.

Fetch the viewer grid with `fetch(results.heightmap_url).then(r => r.json())`. It contains `width`, `height`, flattened `heights`, the elevation range, nodata, and units. The backend always converts an absolute DSM to this bounded JSON form and copies Person 2's JSON for relative-elevation jobs.

The result discovery accepts both the specification names (`fused_dsm.*`, `dsm_preview.png`) and the current Person 3 names (`absolute_dsm.tif`, `preview_dsm.png`). Ordinary PNG/JPEG and uncalibrated GeoTIFF jobs use Person 2's relative heightmap; calibrated GeoTIFF jobs use Person 3's absolute DSM.

## Errors and safety

Unsupported extensions and invalid signatures return 400, oversized uploads return 413, and missing jobs/files return 404. Pipeline failures are recorded with the failed stage and a safe, actionable message at `/api/status/{job_id}`. Full stdout/stderr is saved in that job's private `status.json` for local debugging but is not exposed to the browser. Generated job IDs, plain-filename checks, fixed job directories, upload signatures, and subprocess argument lists prevent common filename and path traversal problems.

CORS permits common localhost frontend ports by default because browsers block cross-origin frontend/API requests unless the API opts in. Set `CORS_ORIGINS` to a comma-separated list for different development hosts.
