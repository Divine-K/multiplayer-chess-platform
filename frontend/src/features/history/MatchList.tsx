import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Avatar } from '../../components/ui/Avatar'
import type { GameSummary, Outcome } from '../../lib/api/types'
import { describeReason, formatDate, formatTimeControl } from '../../lib/format'

const OUTCOMES: Record<Outcome, { label: string; style: string }> = {
  win: { label: 'Won', style: 'bg-ok/15 text-ok' },
  loss: { label: 'Lost', style: 'bg-danger/15 text-danger' },
  draw: { label: 'Draw', style: 'bg-surface-700 text-ink-300' },
}

export function MatchList({ games }: { games: GameSummary[] }) {
  return (
    <ul className="divide-y divide-line">
      {games.map((game) => (
        <li key={game.game_id}>
          <Link to={`/game/${game.game_id}`} className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-800 sm:px-5">
            <span className={`w-14 shrink-0 rounded-md py-1 text-center text-xs font-semibold ${OUTCOMES[game.outcome].style}`}>
              {OUTCOMES[game.outcome].label}
            </span>
            <span className="max-sm:hidden">
              <Avatar username={game.opponent.username} size="sm" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">vs {game.opponent.username}</span>
              <span className="block truncate text-xs text-ink-500">
                As {game.color} · {describeReason(game.result_reason)}
              </span>
            </span>
            <span className="shrink-0 text-right text-xs text-ink-500">
              <span className="block">
                {formatTimeControl(game.time_control_seconds, game.increment_seconds)} · {Math.ceil(game.move_count / 2)}{' '}
                {Math.ceil(game.move_count / 2) === 1 ? 'move' : 'moves'}
              </span>
              <span className="block">{formatDate(game.finished_at)}</span>
            </span>
            <ChevronRight aria-hidden="true" className="size-4 shrink-0 text-ink-500 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function MatchListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading games" className="space-y-3 p-5">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-md bg-surface-700/70" />
      ))}
    </div>
  )
}
