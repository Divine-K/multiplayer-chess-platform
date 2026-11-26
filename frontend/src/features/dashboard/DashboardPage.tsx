import { ArrowRight, Radio } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Avatar } from '../../components/ui/Avatar'
import { buttonStyles } from '../../components/ui/buttonStyles'
import { ErrorNotice } from '../../components/ui/ErrorNotice'
import { gamesApi } from '../../lib/api/games'
import { formatDate } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useCurrentUser } from '../auth/authContext'
import { MatchList, MatchListSkeleton } from '../history/MatchList'
import { useMatchmaking } from '../matchmaking/matchmakingContext'
import { PlayPanel } from './PlayPanel'
import { StatsPanel } from './StatsPanel'

const ACTIVE_GAME_REFRESH_MS = 5000

export function DashboardPage() {
  const user = useCurrentUser()
  const { error: searchError } = useMatchmaking()
  const active = useAsync('active', (signal) => gamesApi.active(signal))
  const statistics = useAsync('statistics', (signal) => gamesApi.statistics(signal))
  const recent = useAsync('recent', (signal) => gamesApi.history(5, 0, signal))

  // A failed search may mean a game already exists (for example, matched from another tab).
  const reloadActive = active.reload
  const seenError = useRef<string | null>(null)
  useEffect(() => {
    if (searchError && searchError !== seenError.current) reloadActive()
    seenError.current = searchError
  }, [searchError, reloadActive])

  // An unfinished game can end, or be cancelled, while this page is open: keep checking on it.
  const hasGame = Boolean(active.data)
  useEffect(() => {
    if (!hasGame) return
    const timer = setInterval(reloadActive, ACTIVE_GAME_REFRESH_MS)
    return () => clearInterval(timer)
  }, [hasGame, reloadActive])

  // Once it is over, the record and recent matches have changed too.
  const reloadStatistics = statistics.reload
  const reloadRecent = recent.reload
  const hadGame = useRef(false)
  useEffect(() => {
    if (hadGame.current && !hasGame) {
      reloadStatistics()
      reloadRecent()
    }
    hadGame.current = hasGame
  }, [hasGame, reloadStatistics, reloadRecent])

  const failed = [active, statistics, recent].filter((request) => request.error)
  const game = active.data
  const opponent = game && (game.players.white.id === user.id ? game.players.black : game.players.white)

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-4">
        <Avatar username={user.username} size="lg" />
        <div className="min-w-0">
          <h1 className="truncate font-display text-3xl font-semibold tracking-tight">{user.username}</h1>
          <p className="text-sm text-ink-500">Member since {formatDate(user.created_at)}</p>
        </div>
      </header>

      {failed.length > 0 && (
        <ErrorNotice message={failed[0].error!} onRetry={() => failed.forEach((request) => request.reload())} />
      )}

      {game && opponent && (
        <section aria-label="Game in progress" className="flex flex-wrap items-center gap-4 rounded-xl border border-accent-500/60 bg-accent-500/10 px-5 py-4">
          <Radio aria-hidden="true" className="size-5 text-accent-400" />
          <p className="flex-1">
            <span className="font-medium">You have a game in progress</span>
            <span className="block text-sm text-ink-300">
              Against {opponent.username}. {game.status === 'active' ? 'Your clock may be running.' : 'It starts when you both arrive.'}
            </span>
          </p>
          <Link to={`/game/${game.game_id}`} className={buttonStyles()}>
            Resume game <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </section>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="space-y-6">
          <PlayPanel disabled={Boolean(game)} />
          <StatsPanel statistics={statistics.data} />
        </div>
        <section aria-labelledby="recent-heading" className="panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
            <h2 id="recent-heading" className="text-sm font-semibold">
              Recent matches
            </h2>
            {(recent.data?.total ?? 0) > 0 && (
              <Link to="/history" className="text-sm text-accent-400 hover:text-accent-300">
                View all {recent.data!.total}
              </Link>
            )}
          </div>
          {recent.loading ? (
            <MatchListSkeleton />
          ) : recent.data && recent.data.items.length > 0 ? (
            <MatchList games={recent.data.items} />
          ) : (
            <p className="px-5 py-12 text-center text-sm text-ink-500">
              {recent.error ? 'Recent matches are unavailable right now.' : 'No games yet. Your finished matches will appear here.'}
            </p>
          )}
        </section>
      </div>
    </div>
  )
}
