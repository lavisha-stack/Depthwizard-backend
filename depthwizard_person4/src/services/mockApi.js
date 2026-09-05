const jobs = new Map()
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function jsonDataUrl(value) {
  return `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(value))}`
}

function demoHeightmap(size = 33) {
  const rawHeights = []
  for (let row = 0; row < size; row += 1) {
    const z = row / (size - 1) * 4 - 2
    for (let column = 0; column < size; column += 1) {
      const x = column / (size - 1) * 4 - 2
      rawHeights.push(0.9 * Math.exp(-(x * x + z * z) * 0.7) + 0.32 * Math.sin(x * 2.2) * Math.cos(z * 1.8) + 0.45 * Math.exp(-((x - 1) ** 2 + (z + 0.7) ** 2) * 2))
    }
  }
  const low = Math.min(...rawHeights)
  const high = Math.max(...rawHeights)
  const heights = rawHeights.map((value) => (value - low) / (high - low))
  return { width: size, height: size, heights, elevation_min: 0, elevation_max: 1, nodata: null, units: 'relative' }
}

const DEMO_HEIGHTMAP_URL = jsonDataUrl(demoHeightmap())
const DEMO_METADATA_URL = jsonDataUrl({ elevation_units: 'relative', is_absolute_elevation: false, target: { width: 33, height: 33, pixel_resolution: null } })

export async function createJob(file) {
  await wait(700)
  const jobId = `demo_${Date.now()}`
  jobs.set(jobId, { started: Date.now(), texture: URL.createObjectURL(file) })
  return { job_id: jobId, status: 'processing', progress: 12 }
}

export async function getJobStatus(jobId) {
  await wait(180)
  const job = jobs.get(jobId)
  if (!job) return { job_id: jobId, status: 'completed', progress: 100 }
  const elapsed = Date.now() - job.started
  const progress = Math.min(100, 22 + Math.floor(elapsed / 35))
  return { job_id: jobId, status: progress >= 100 ? 'completed' : 'depth_estimation', progress }
}

export async function getJobResults(jobId) {
  await wait(250)
  const job = jobs.get(jobId)
  return {
    job_id: jobId,
    status: 'completed',
    input_type: 'image',
    is_georeferenced: false,
    width: 2048,
    height: 1536,
    depth_model: 'Demo pipeline',
    texture_url: job?.texture || null,
    depth_preview_url: job?.texture || null,
    dsm_preview_url: job?.texture || null,
    heightmap_url: DEMO_HEIGHTMAP_URL,
    metadata_url: DEMO_METADATA_URL,
    dsm_download_url: null,
  }
}
