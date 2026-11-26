import { Link } from 'react-router-dom'
import { BRAND } from '../../lib/brand'

export function Logo({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} className="inline-flex items-center gap-2.5" aria-label={`${BRAND.name} home`}>
      <svg viewBox="0 0 28 28" className="size-7" aria-hidden="true">
        <rect width="28" height="28" rx="7" fill="var(--color-accent-500)" />
        <path d="M6 6h8v8H6zM14 14h8v8h-8z" fill="var(--color-surface-950)" />
      </svg>
      <span className="font-display text-xl font-semibold tracking-tight">{BRAND.name}</span>
    </Link>
  )
}
