import { Link } from 'react-router-dom'

const steps = ['Upload RGB', 'Estimate depth', 'Calibrate elevation', 'Generate DSM', 'Explore in 3D']

export default function HomePage() {
  return (
    <main>
      <section className="hero page-width">
        <div className="hero-copy">
          <div className="signal-label"><span /> SINGLE-VIEW TERRAIN INTELLIGENCE</div>
          <h1>Turn one image into an <em>interactive 3D terrain.</em></h1>
          <p>DepthWizard estimates scene depth, calibrates elevation where reference data is available, and delivers an explorable surface model in minutes.</p>
          <div className="hero-actions"><Link className="primary-button" to="/analyze">Analyze an image <span>→</span></Link><a className="text-link" href="#pipeline">See how it works ↓</a></div>
          <div className="trust-row"><span>◈ GeoTIFF ready</span><span>⌁ SRTM + GCP calibration</span><span>△ 3D flythrough</span></div>
        </div>
        <div className="hero-visual" aria-label="Conceptual terrain elevation visualization">
          <div className="visual-toolbar"><span>SCENE / ELEVATION</span><span className="live-dot">● LIVE</span></div>
          <div className="terrain-map"><div className="crosshair">+</div><div className="altitude a1">142.8 m</div><div className="altitude a2">118.4 m</div><div className="scan-line" /></div>
          <div className="visual-footer"><span>LAT 28.6139° N</span><span>GRID 512 × 512</span><span>ΔZ 24.4 M</span></div>
        </div>
      </section>

      <section className="pipeline-section page-width" id="pipeline">
        <div className="section-heading"><div><span className="eyebrow">THE PIPELINE</span><h2>From pixels to elevation</h2></div><p>One continuous workflow. Each stage preserves the spatial grid for the next.</p></div>
        <div className="pipeline-flow">{steps.map((step, index) => <div className="pipeline-step" key={step}><span>0{index + 1}</span><strong>{step}</strong>{index < steps.length - 1 && <i>→</i>}</div>)}</div>
      </section>

      <section className="explain-section page-width">
        <article className="explain-card"><span className="eyebrow">WHAT IS DEPTHWIZARD?</span><h2>Height insight where depth data is missing.</h2><p>A standard RGB image records color, not height. DepthWizard uses monocular depth estimation to recover relative scene structure, then calibrates it toward approximate real elevation when geospatial reference data is available.</p><p>The resulting estimated DSM becomes a textured 3D surface for rapid visual analysis and flythroughs.</p></article>
        <div className="feature-grid"><article><b>01</b><h3>Single-view depth</h3><p>Estimate relative scene geometry from one RGB image.</p></article><article><b>02</b><h3>Spatially aware</h3><p>Preserve GeoTIFF metadata and support reference calibration.</p></article><article><b>03</b><h3>Built to explore</h3><p>Hand elevation and texture data directly to the 3D viewer.</p></article><article><b>04</b><h3>Honest outputs</h3><p>Designed for visualization and rapid analysis, not surveying.</p></article></div>
      </section>
    </main>
  )
}
