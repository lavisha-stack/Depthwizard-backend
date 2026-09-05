# DepthWizard Person 4 — Frontend

This React + Vite website owns the user experience: explain DepthWizard, accept an image, call Person 5's API, show processing state, present results, and provide an isolated mounting point for Person 6's terrain renderer. It does not contain depth, calibration, DSM, or mesh algorithms.

## Project map

- `src/pages/` contains the Home, Analyze, and Results routes.
- `src/components/` contains the upload, preview, status, metadata, error, navigation, and viewer UI.
- `src/services/api.js` selects real or mock mode and exports the stable API interface.
- `src/services/realApi.js` is the only file that knows Person 5's endpoint paths.
- `src/services/mockApi.js` provides an explicit offline presentation mode.
- `src/components/TerrainViewer.jsx` is the only component coupled to Person 6's viewer contract.
- `src/styles/global.css` contains the responsive visual system.

## Install and run

```bash
npm install
npm run dev
```

Open `http://localhost:5173`. Create a local `.env` by copying `.env.example` if the defaults need changing.

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_POLL_INTERVAL_MS=2000
VITE_MAX_UPLOAD_SIZE_MB=500
VITE_USE_MOCK_API=false
```

The backend must allow `http://localhost:5173` through CORS. Build the production bundle with `npm run build`; preview it locally with `npm run preview`.

## Person 5 API contract

The frontend sends multipart `FormData` with the required field `image` to `POST /api/process`. A synchronous completed response is supported immediately. If the response is still processing, the frontend polls `GET /api/status/{jobId}` every configured interval, stops on `completed` or `failed`, and then reads `GET /api/results/{jobId}`.

Expected result fields are flat, matching the current Person 5 module:

```json
{
  "job_id": "job_7f82a91c1234",
  "status": "completed",
  "is_georeferenced": true,
  "width": 2048,
  "height": 1536,
  "depth_preview_url": "/api/files/job_x/relative_depth_preview.png",
  "dsm_preview_url": "/api/files/job_x/preview_dsm.png",
  "dsm_download_url": "/api/files/job_x/absolute_dsm.tif",
  "heightmap_url": "/api/files/job_x/heightmap.json",
  "texture_url": "/api/files/job_x/rgb_model.png"
}
```

Relative and absolute URLs are both supported. During development, backend asset URLs are proxied through Vite; production retains the configured API origin. If endpoint names change, edit only `src/services/realApi.js`. GCP and SRTM uploads are wired to Person 5 and require a georeferenced GeoTIFF source.

## Person 6 viewer handoff

`TerrainViewer.jsx` lazy-loads Person 6's real Three.js module and passes `container`, `heightmapUrl`, `textureUrl`, and `metadataUrl` directly to it:

```js
const viewer = await createTerrainViewer({ container, heightmapUrl, textureUrl, metadataUrl })
viewer.destroy()
```

The wrapper initializes inside a React effect, calls `destroy()` during cleanup, and exposes a retryable error state. The viewer provides texture/elevation/wireframe modes, orbit overview and first-person movement, automatic flythrough controls, and a centre-reticle probe with point value, slope, and source pixel. Relative output is clearly labelled and limited to 0.2×–2× visual relief; calibrated metric DSMs support up to 5×.

## Demo mode

Set `VITE_USE_MOCK_API=true` and restart Vite. Mock mode simulates upload, polling, results, and failure-safe empty states without silently replacing the real API. Set it back to `false` for the final integrated demonstration.

## Complete user flow

1. Open the overview and select **Analyze an image**.
2. Drop or browse for PNG, JPEG, or TIFF input.
3. Review the preview, then select **Generate 3D terrain**.
4. Watch the real backend status and progress when supplied.
5. On completion, compare RGB and elevation previews, inspect metadata, open downloads, and use the embedded Person 6 viewer.
