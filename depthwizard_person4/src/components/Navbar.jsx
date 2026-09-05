import { Link, NavLink } from 'react-router-dom'

export default function Navbar() {
  return (
    <header className="navbar">
      <Link className="brand" to="/" aria-label="DepthWizard home">
        <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
        <span>Depth<span>Wizard</span></span>
      </Link>
      <nav aria-label="Main navigation">
        <NavLink to="/" end>Overview</NavLink>
        <NavLink to="/analyze">Analyze</NavLink>
      </nav>
      <Link className="nav-cta" to="/analyze">New analysis <span>↗</span></Link>
    </header>
  )
}
