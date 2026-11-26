import { apiRequest } from './client'
import type {
  GameHistoryPage,
  GameState,
  MatchmakingStatus,
  PublicProfile,
  Statistics,
  TimeControl,
} from './types'

export const gamesApi = {
  active: (signal?: AbortSignal) => apiRequest<GameState | null>('/api/v1/games/active', { signal }),

  history: (limit: number, offset: number, signal?: AbortSignal) =>
    apiRequest<GameHistoryPage>(`/api/v1/games/history?limit=${limit}&offset=${offset}`, { signal }),

  statistics: (signal?: AbortSignal) => apiRequest<Statistics>('/api/v1/users/me/statistics', { signal }),

  profile: (username: string, signal?: AbortSignal) =>
    apiRequest<PublicProfile>(`/api/v1/users/${encodeURIComponent(username)}`, { signal }),
}

export const matchmakingApi = {
  timeControls: (signal?: AbortSignal) =>
    apiRequest<TimeControl[]>('/api/v1/matchmaking/time-controls', { authenticated: false, signal }),

  join: (control: Pick<TimeControl, 'time_control_seconds' | 'increment_seconds'>) =>
    apiRequest<MatchmakingStatus>('/api/v1/matchmaking', {
      method: 'POST',
      body: {
        time_control_seconds: control.time_control_seconds,
        increment_seconds: control.increment_seconds,
      },
    }),

  status: (signal?: AbortSignal) => apiRequest<MatchmakingStatus>('/api/v1/matchmaking/status', { signal }),

  cancel: () => apiRequest<MatchmakingStatus>('/api/v1/matchmaking', { method: 'DELETE' }),
}
