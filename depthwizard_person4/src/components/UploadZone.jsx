import { useRef, useState } from 'react'
import { MAX_UPLOAD_SIZE_MB } from '../services/api'

export default function UploadZone({ file, onFile, error }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  function accept(event) {
    event.preventDefault()
    setDragging(false)
    const next = event.dataTransfer?.files?.[0] || event.target.files?.[0]
    if (next) onFile(next)
    if (event.target === inputRef.current) event.target.value = ''
  }

  return (
    <div
      className={`upload-zone ${dragging ? 'is-dragging' : ''} ${error ? 'has-error' : ''}`}
      onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={accept}
    >
      <input ref={inputRef} type="file" accept=".png,.jpg,.jpeg,.tif,.tiff,image/png,image/jpeg,image/tiff" onChange={accept} hidden />
      <div className="upload-glyph" aria-hidden="true">⌁</div>
      <div>
        <h3>{file ? 'Change source image' : 'Drop your terrain image here'}</h3>
        <p>PNG, JPEG, or GeoTIFF · up to {MAX_UPLOAD_SIZE_MB} MB</p>
      </div>
      <button className="secondary-button" type="button" onClick={() => inputRef.current?.click()}>
        {file ? 'Choose another' : 'Browse files'}
      </button>
      {error && <p className="field-error" role="alert">{error}</p>}
    </div>
  )
}
