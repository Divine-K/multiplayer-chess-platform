import { createContext, useContext } from 'react'
import type { TimeControl } from '../../lib/api/types'

export type SearchControl = Pick<TimeControl, 'time_control_seconds' | 'increment_seconds'>

export type SearchState =
  | { phase: 'idle' }
  | { phase: 'joining'; control: SearchControl }
  | { phase: 'queued'; control: SearchControl; since: number; cancelling: boolean }

export interface MatchmakingValue {
  search: SearchState
  error: string | null
  start: (control: SearchControl) => Promise<void>
  cancel: () => Promise<void>
}

export const MatchmakingContext = createContext<MatchmakingValue | null>(null)

export function useMatchmaking(): MatchmakingValue {
  const value = useContext(MatchmakingContext)
  if (!value) throw new Error('useMatchmaking must be used inside <MatchmakingProvider>')
  return value
}
