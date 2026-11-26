import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { buttonStyles } from '../../components/ui/buttonStyles'
import { ErrorNotice } from '../../components/ui/ErrorNotice'
import { gamesApi } from '../../lib/api/games'
import { useAsync } from '../../lib/useAsync'
import { MatchList, MatchListSkeleton } from './MatchList'

export const PAGE_SIZE = 10

export function HistoryPage() {
  const [page, setPage] = useState(0)
  const history = useAsync(`history:${page}`, (signal) => gamesApi.history(PAGE_SIZE, page * PAGE_SIZE, signal))
  const total = history.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold tracking-tight">Match history</h1>
      <p className="mt-1 text-ink-500">Your finished games, newest first. Open one to see the final position and moves.</p>

      <div className="mt-6 space-y-4">
        {history.error && <ErrorNotice message={history.error} onRetry={history.reload} />}
        <section aria-label="Games" aria-busy={history.loading} className="panel overflow-hidden">
          {history.loading ? (
            <MatchListSkeleton rows={6} />
          ) : history.data && history.data.items.length > 0 ? (
            <MatchList games={history.data.items} />
          ) : !history.error ? (
            <div className="px-6 py-14 text-center">
              <p className="font-medium">No finished games yet</p>
              <p className="mt-1 text-sm text-ink-500">Your results will appear here after your first game.</p>
              <Link to="/play" className={`${buttonStyles()} mt-5`}>
                Play Chess
              </Link>
            </div>
          ) : null}
        </section>

        {total > PAGE_SIZE && (
          <nav aria-label="Pagination" className="flex items-center justify-between text-sm text-ink-500">
            <Button variant="secondary" disabled={page === 0 || history.loading} onClick={() => setPage(page - 1)}>
              Newer
            </Button>
            <span>
              Page {page + 1} of {pages}
            </span>
            <Button variant="secondary" disabled={page + 1 >= pages || history.loading} onClick={() => setPage(page + 1)}>
              Older
            </Button>
          </nav>
        )}
      </div>
    </div>
  )
}
