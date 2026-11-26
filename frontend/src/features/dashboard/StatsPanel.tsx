import type { Statistics } from '../../lib/api/types'
import { Skeleton } from '../../components/ui/Skeleton'

const SEGMENTS = [
  { key: 'wins', label: 'Wins', bar: 'bg-ok' },
  { key: 'draws', label: 'Draws', bar: 'bg-ink-500' },
  { key: 'losses', label: 'Losses', bar: 'bg-danger' },
] as const

export function StatsPanel({ statistics }: { statistics: Statistics | null }) {
  return (
    <section aria-labelledby="record-heading" className="panel p-5">
      <div className="flex items-baseline justify-between">
        <h2 id="record-heading" className="text-sm font-semibold">
          Your record
        </h2>
        {statistics && (
          <span className="text-xs text-ink-500">
            {statistics.games_played} {statistics.games_played === 1 ? 'game' : 'games'} played
          </span>
        )}
      </div>

      {!statistics ? (
        <Skeleton className="mt-4 h-24" />
      ) : (
        <>
          <dl className="mt-4 grid grid-cols-3 gap-3 text-center">
            {SEGMENTS.map((segment) => (
              <div key={segment.key} className="flex flex-col-reverse rounded-lg bg-surface-800 py-3">
                <dt className="text-xs text-ink-500">{segment.label}</dt>
                <dd className="font-display text-3xl font-semibold tabular-nums">{statistics[segment.key]}</dd>
              </div>
            ))}
          </dl>
          {statistics.games_played > 0 ? (
            <>
              <div aria-hidden="true" className="mt-4 flex h-1.5 gap-0.5 overflow-hidden rounded-full">
                {SEGMENTS.map(
                  (segment) =>
                    statistics[segment.key] > 0 && (
                      <div key={segment.key} className={segment.bar} style={{ flexGrow: statistics[segment.key] }} />
                    ),
                )}
              </div>
              <p className="mt-2 text-xs text-ink-500">
                Win rate {Math.round((statistics.wins / statistics.games_played) * 100)}%
              </p>
            </>
          ) : (
            <p className="mt-4 text-sm text-ink-500">Play your first game to start building a record.</p>
          )}
        </>
      )}
    </section>
  )
}
