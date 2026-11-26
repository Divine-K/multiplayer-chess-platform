import { MotionConfig } from 'framer-motion'
import { useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { ToastProvider } from './components/ui/ToastProvider'
import { AuthProvider } from './features/auth/AuthProvider'
import { RedirectIfAuthenticated, RequireAuth } from './features/auth/guards'
import { LoginPage } from './features/auth/LoginPage'
import { RegisterPage } from './features/auth/RegisterPage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { GamePage } from './features/game/GamePage'
import { HistoryPage } from './features/history/HistoryPage'
import { LandingPage } from './features/landing/LandingPage'
import { MatchmakingProvider } from './features/matchmaking/MatchmakingProvider'
import { NotFoundPage } from './features/NotFoundPage'
import { BRAND } from './lib/brand'

const TITLES: Record<string, string> = {
  '/login': 'Sign in',
  '/register': 'Create account',
  '/play': 'Play',
  '/history': 'Match history',
}

/** Starts each new page at the top and names it for tabs and screen readers. */
function useRouteEffects() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo?.(0, 0)
    const page = pathname.startsWith('/game/') ? 'Game' : TITLES[pathname]
    document.title = page ? `${page} · ${BRAND.name}` : `${BRAND.name} · Real-time multiplayer chess`
  }, [pathname])
}

function SignedInLayout() {
  return (
    <MatchmakingProvider>
      <AppShell />
    </MatchmakingProvider>
  )
}

/** Everything except the router itself, so tests can supply their own. */
export default function App() {
  useRouteEffects()
  return (
    <MotionConfig reducedMotion="user">
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route element={<RedirectIfAuthenticated />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
            </Route>
            <Route element={<RequireAuth />}>
              <Route element={<SignedInLayout />}>
                <Route path="/play" element={<DashboardPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/game/:gameId" element={<GamePage />} />
              </Route>
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </MotionConfig>
  )
}
