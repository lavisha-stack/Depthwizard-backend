export default function ErrorMessage({ message, onRetry }) {
  return (
    <div className="error-card" role="alert">
      <span className="error-icon">!</span>
      <div><strong>Terrain generation failed</strong><p>{message || 'Please check the image and try again.'}</p></div>
      {onRetry && <button type="button" className="secondary-button" onClick={onRetry}>Try again</button>}
    </div>
  )
}
