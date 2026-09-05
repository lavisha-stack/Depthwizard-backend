import { API_BASE_URL } from './api'

async function request(path, options) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options)
  } catch {
    throw new Error('Cannot reach the DepthWizard backend. Check that it is running.')
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(typeof body.detail === 'string' ? body.detail : body.detail?.message || `Request failed (${response.status}).`)
    Object.assign(error, body)
    throw error
  }
  return body
}

export function createJob(file, advanced = {}) {
  const form = new FormData()
  form.append('image', file)
  if (advanced.gcp) form.append('gcp', advanced.gcp)
  if (advanced.srtm) form.append('srtm', advanced.srtm)
  return request('/api/process', { method: 'POST', body: form })
}

export function getJobStatus(jobId) {
  return request(`/api/status/${encodeURIComponent(jobId)}`)
}

export function getJobResults(jobId) {
  return request(`/api/results/${encodeURIComponent(jobId)}`)
}
