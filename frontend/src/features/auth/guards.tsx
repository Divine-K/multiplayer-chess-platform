import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { ErrorNotice } from '../../components/ui/ErrorNotice'
import { Spinner } from '../../components/ui/Spinner'
import { useAuth } from './authContext'

function SessionCheck() {
  return (
    <div role="status" className="grid min-h-screen place-items-center text-ink-500">
      <span className="flex items-center gap-3">
        <Spinner /> Restoring your session…
      </span>
    </div>
  )
}

export function RequireAuth() {
  const { state, retry } = useAuth()
  const location = useLocation()

  if (state.status === 'loading') return <SessionCheck />
  if (state.status === 'unreachable') {
    return (
      <div className="mx-auto grid min-h-screen max-w-md place-items-center px-6">
        <ErrorNotice message={state.message} onRetry={retry} />
      </div>
    )
  }
  if (state.status === 'anonymous') {
    if (state.signedOut) return <Navigate to="/" replace />
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}

/** Keeps signed-in users away from the sign-in screens, returning them where they were headed. */
export function RedirectIfAuthenticated() {
  const { state } = useAuth()
  const location = useLocation()

  if (state.status === 'loading') return <SessionCheck />
  if (state.status === 'authenticated') {
    const from = (location.state as { from?: unknown } | null)?.from
    return <Navigate to={typeof from === 'string' ? from : '/play'} replace />
  }
  return <Outlet />
}
