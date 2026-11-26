import type { ClockInfo, GameState, MoveInfo } from '../../../lib/api/types'
import type { PlayerColor } from '../chess'

type Message<T extends string, P> = { type: T; game_id: string; payload: P }

export type ServerMessage =
  | Message<'connected', { color: PlayerColor; opponent_connected: boolean; state: GameState }>
  | Message<'player_connected' | 'player_disconnected', { color: PlayerColor }>
  | Message<'game_started' | 'draw_declined' | 'state', { state: GameState }>
  | Message<'draw_offered', { by: PlayerColor; state: GameState }>
  | Message<'game_finished', { state: GameState }>
  | Message<'move_accepted', { move: MoveInfo & { color: PlayerColor }; state: GameState }>
  | Message<'move_rejected', { code: string; message: string; state: GameState }>
  | Message<'turn_changed', { turn: PlayerColor; ply: number; version: number }>
  | Message<'clock_updated', { clocks: ClockInfo; version: number; server_time: string }>
  | Message<'pong', Record<string, never>>
  | Message<'closing', { code: number }>
  | Message<'error', { code: string; message: string }>
