import { History, LogOut, Swords, X } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth, useCurrentUser } from '../../features/auth/authContext'
import { useMatchmaking } from '../../features/matchmaking/matchmakingContext'
import { useElapsedSeconds } from '../../features/matchmaking/useElapsedSeconds'
import { formatTimeControl } from '../../lib/format'
import { Avatar } from '../ui/Avatar'
import { Spinner } from '../ui/Spinner'
import { Logo } from './Logo'

const NAV = [
  { to: '/play', label: 'Play', icon: Swords },
  { to: '/history', label: 'History', icon: History },
]

/** Keeps a running search visible (and cancellable) away from the dashboard. */
function SearchIndicator({ since, label }: { since: number; label: string }) {
  const { cancel } = useMatchmaking()
  const elapsed = useElapsedSeconds(since)
  return (
    <div className="border-b border-line bg-surface-900">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2 text-sm sm:px-6">
        <Spinner className="size-4 text-accent-400" />
        <Link to="/play" className="flex-1 text-ink-300 hover:text-ink-100">
          Searching for a {label} game · {elapsed}s
        </Link>
        <button type="button" onClick={cancel} className="inline-flex items-center gap-1 text-ink-500 hover:text-ink-100">
          <X aria-hidden="true" className="size-4" /> Cancel search
        </button>
      </div>
    </div>
  )
}

export function AppShell() {
  const user = useCurrentUser()
  const { logout } = useAuth()
  const { search, cancel } = useMatchmaking()
  const location = useLocation()

  async function handleSignOut() {
    // Leave the queue while we still hold a token, so nobody gets paired with an absent player.
    if (search.phase !== 'idle') await cancel()
    logout()
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-line">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-2 px-4 sm:gap-6 sm:px-6">
          <Logo to="/play" />
          <nav aria-label="Main" className="ml-2 flex gap-1">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isActive ? 'bg-surface-800 text-ink-100' : 'text-ink-500 hover:text-ink-100'}`
                }
              >
                <Icon aria-hidden="true" className="size-4" />
                <span className="max-sm:sr-only">{label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span className="flex items-center gap-2.5">
              <Avatar username={user.username} size="sm" />
              <span className="max-w-40 truncate text-sm font-medium max-md:sr-only">{user.username}</span>
            </span>
            <button
              type="button"
              onClick={handleSignOut}
              aria-label="Sign out"
              title="Sign out"
              className="rounded-lg p-2 text-ink-500 hover:bg-surface-800 hover:text-ink-100"
            >
              <LogOut aria-hidden="true" className="size-4" />
            </button>
          </div>
        </div>
      </header>
      {search.phase === 'queued' && location.pathname !== '/play' && (
        <SearchIndicator
          since={search.since}
          label={formatTimeControl(search.control.time_control_seconds, search.control.increment_seconds)}
        />
      )}
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}
