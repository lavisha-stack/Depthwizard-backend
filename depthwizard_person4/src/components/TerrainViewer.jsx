import { useEffect, useRef, useState } from 'react'
import { createTerrainViewer } from '../../../depthwizard_person6/src/main.js'

export default function TerrainViewer({ heightmapUrl, textureUrl, metadataUrl }) {
  const mountRef = useRef(null)
  const [viewerState, setViewerState] = useState({ status: 'loading', message: '' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!heightmapUrl || !mountRef.current) return undefined
    let viewer
    let cancelled = false
    mountRef.current.replaceChildren()
    setViewerState({ status: 'loading', message: '' })
    createTerrainViewer({ container: mountRef.current, heightmapUrl, textureUrl, metadataUrl })
      .then((created) => {
        if (cancelled) created?.destroy?.()
        else { viewer = created; setViewerState({ status: 'ready', message: '' }) }
      })
      .catch((error) => {
        if (!cancelled) setViewerState({ status: 'error', message: error?.message || 'The terrain renderer could not start.' })
      })
    return () => {
      cancelled = true
      viewer?.destroy?.()
      if (!viewer) mountRef.current?.replaceChildren()
    }
  }, [heightmapUrl, textureUrl, metadataUrl, attempt])

  if (!heightmapUrl) return <div className="viewer-unavailable"><span>3D</span><h3>Terrain data unavailable</h3><p>The rest of this analysis is still available.</p></div>

  return (
    <div className="terrain-viewer">
      <div className="terrain-viewer-mount" ref={mountRef} />
      {viewerState.status === 'loading' && <div className="viewer-handoff"><div className="terrain-lines" aria-hidden="true" /><span className="status-pill">LOADING 3D VIEWER</span><h3>Building interactive terrain</h3><p>Preparing the heightmap and texture.</p></div>}
      {viewerState.status === 'error' && <div className="viewer-handoff viewer-error" role="alert"><span className="status-pill">3D VIEWER ERROR</span><h3>Terrain could not be displayed</h3><p>{viewerState.message}</p><button className="secondary-button" type="button" onClick={() => setAttempt((value) => value + 1)}>Retry viewer</button></div>}
    </div>
  )
}
