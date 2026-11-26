import { useLocation } from 'react-router-dom'

/** Exposes the current path so tests can assert on navigation. */
export function LocationProbe() {
  return <div data-testid="location">{useLocation().pathname}</div>
}
