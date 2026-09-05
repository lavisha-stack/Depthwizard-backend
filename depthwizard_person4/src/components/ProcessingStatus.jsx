const stages = {
  uploaded: 'Uploading source image',
  queued: 'Waiting for the processing worker',
  processing: 'Preparing analysis',
  preprocessing: 'Preprocessing image',
  depth_estimation: 'Estimating monocular depth',
  calibration: 'Calibrating elevation',
  completed: 'Terrain ready',
}

export default function ProcessingStatus({ status, progress }) {
  const hasProgress = Number.isFinite(progress)
  return (
    <section className="processing-card" aria-live="polite">
      <div className="scanner"><span /><span /><span /></div>
      <div className="processing-copy">
        <span className="eyebrow">PIPELINE ACTIVE</span>
        <h2>Generating terrain…</h2>
        <p>{stages[status] || 'Processing scene data'}</p>
        <div className={`progress-track ${hasProgress ? '' : 'indeterminate'}`}>
          <span style={hasProgress ? { width: `${Math.max(2, Math.min(100, progress))}%` } : undefined} />
        </div>
        <div className="progress-label"><span>{status?.replaceAll('_', ' ')}</span>{hasProgress && <strong>{progress}%</strong>}</div>
      </div>
    </section>
  )
}
