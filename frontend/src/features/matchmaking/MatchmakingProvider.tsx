import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../../components/ui/toastContext'
import { ApiError } from '../../lib/api/client'
import { matchmakingApi } from '../../lib/api/games'
import type { MatchmakingStatus } from '../../lib/api/types'
import { MatchmakingContext, type SearchControl, type SearchState } from './matchmakingContext'

export const POLL_INTERVAL_MS = 2000

function queuedFrom(status: MatchmakingStatus): SearchState {
  const elapsed = status.queued_since ? Date.now() - Date.parse(status.queued_since) : 0
  return {
    phase: 'queued',
    control: {
      time_control_seconds: status.time_control_seconds ?? 0,
      increment_seconds: status.increment_seconds ?? 0,
    },
    since: Date.now() - Math.max(0, elapsed),
    cancelling: false,
  }
}

const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : 'Something went wrong.')

/**
 * Owns the matchmaking search. It lives above the pages so that moving between them does not
 * abandon a search: each status poll is also the heartbeat that keeps the queue entry alive.
 */
export function MatchmakingProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const toast = useToast()
  const [search, setSearch] = useState<SearchState>({ phase: 'idle' })
  const [error, setError] = useState<string | null>(null)
  // Incremented by every start or cancel so that late poll responses are ignored.
  const generation = useRef(0)

  const enterGame = useCallback(
    (gameId: string, message: string) => {
      generation.current += 1
      setSearch({ phase: 'idle' })
      toast(message, 'success')
      navigate(`/game/${gameId}`)
    },
    [navigate, toast],
  )

  // Resume a search that is still queued, for example after a page refresh.
  useEffect(() => {
    const controller = new AbortController()
    const startedAt = generation.current
    matchmakingApi.status(controller.signal).then(
      (status) => {
        if (generation.current === startedAt && status.status === 'queued') setSearch(queuedFrom(status))
      },
      () => {}, // the dashboard reports connectivity problems through its own requests
    )
    return () => controller.abort()
  }, [])

  const queued = search.phase === 'queued' && !search.cancelling

  useEffect(() => {
    if (!queued) return
    const mine = generation.current
    let stopped = false
    let timer: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const status = await matchmakingApi.status()
        if (stopped || generation.current !== mine) return
        setError(null)
        if (status.status === 'matched' && status.game_id) {
          enterGame(status.game_id, 'Opponent found. Good luck!')
          return
        }
        if (status.status === 'idle') {
          setSearch({ phase: 'idle' })
          toast('Your search expired. Start a new one when you are ready.')
          return
        }
      } catch (failure) {
        if (stopped || generation.current !== mine) return
        setError(messageOf(failure))
      }
      timer = setTimeout(poll, POLL_INTERVAL_MS)
    }

    timer = setTimeout(poll, POLL_INTERVAL_MS)
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [queued, enterGame, toast])

  const start = useCallback(
    async (control: SearchControl) => {
      const mine = ++generation.current
      setError(null)
      setSearch({ phase: 'joining', control })
      try {
        const status = await matchmakingApi.join(control)
        if (generation.current !== mine) return
        if (status.status === 'matched' && status.game_id) {
          enterGame(status.game_id, 'Opponent found. Good luck!')
        } else {
          setSearch(queuedFrom(status))
        }
      } catch (failure) {
        if (generation.current !== mine) return
        setSearch({ phase: 'idle' })
        setError(messageOf(failure))
      }
    },
    [enterGame],
  )

  const cancel = useCallback(async () => {
    const mine = ++generation.current
    setSearch((current) => (current.phase === 'queued' ? { ...current, cancelling: true } : current))
    try {
      const status = await matchmakingApi.cancel()
      if (generation.current !== mine) return
      if (status.status === 'matched' && status.game_id) {
        enterGame(status.game_id, 'A match was made before you cancelled.')
        return
      }
      setError(null)
      setSearch({ phase: 'idle' })
    } catch (failure) {
      if (generation.current !== mine) return
      setError(messageOf(failure))
      setSearch((current) => (current.phase === 'queued' ? { ...current, cancelling: false } : current))
    }
  }, [enterGame])

  const value = useMemo(() => ({ search, error, start, cancel }), [search, error, start, cancel])

  return <MatchmakingContext.Provider value={value}>{children}</MatchmakingContext.Provider>
}
