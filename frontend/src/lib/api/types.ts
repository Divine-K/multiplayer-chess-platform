/** Mirrors the backend's response schemas (see docs/API.md). */

import type { PlayerColor } from '../../features/game/chess'

export type GameStatus = 'waiting' | 'active' | 'finished' | 'aborted'
export type GameResult = 'white_win' | 'black_win' | 'draw'
export type Outcome = 'win' | 'loss' | 'draw'
export type ResultReason =
  | 'checkmate'
  | 'stalemate'
  | 'insufficient_material'
  | 'threefold_repetition'
  | 'fifty_move_rule'
  | 'resignation'
  | 'timeout'
  | 'timeout_vs_insufficient_material'
  | 'draw_agreement'
  | 'never_started'

export interface PlayerInfo {
  id: number
  username: string
}

export interface MoveInfo {
  ply: number
  uci: string
  san: string
}

export interface ClockInfo {
  white_ms: number
  black_ms: number
  running: PlayerColor | null
}

export interface GameState {
  game_id: string
  status: GameStatus
  version: number
  time_control_seconds: number
  increment_seconds: number
  players: { white: PlayerInfo; black: PlayerInfo }
  fen: string
  turn: PlayerColor
  ply: number
  moves: MoveInfo[]
  last_move: string | null
  is_check: boolean
  legal_moves: string[]
  captured: { white: string[]; black: string[] }
  clocks: ClockInfo
  draw_offered_by: PlayerColor | null
  result: GameResult | null
  result_reason: ResultReason | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  server_time: string
}

export interface GameSummary {
  game_id: string
  color: PlayerColor
  opponent: PlayerInfo
  outcome: Outcome
  result: GameResult
  result_reason: ResultReason
  time_control_seconds: number
  increment_seconds: number
  move_count: number
  finished_at: string
}

export interface GameHistoryPage {
  items: GameSummary[]
  total: number
  limit: number
  offset: number
}

export interface Statistics {
  games_played: number
  wins: number
  losses: number
  draws: number
}

export interface TimeControl {
  time_control_seconds: number
  increment_seconds: number
  label: string
}

export interface MatchmakingStatus {
  status: 'idle' | 'queued' | 'matched'
  game_id: string | null
  color: PlayerColor | null
  time_control_seconds: number | null
  increment_seconds: number | null
  queued_since: string | null
}

export interface PublicProfile {
  id: number
  username: string
  created_at: string
  statistics: Statistics
}
