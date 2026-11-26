import type { User } from '../lib/api/auth'
import type { GameState, GameSummary, MatchmakingStatus, Statistics } from '../lib/api/types'

export const GAME_ID = '11111111-2222-3333-4444-555555555555'

export const alice: User = { id: 1, username: 'alice', email: 'alice@example.org', created_at: '2026-01-15T12:00:00Z' }

export const noStats: Statistics = { games_played: 0, wins: 0, losses: 0, draws: 0 }

export const idle: MatchmakingStatus = {
  status: 'idle',
  game_id: null,
  color: null,
  time_control_seconds: null,
  increment_seconds: null,
  queued_since: null,
}

export const timeControls = [180, 300, 600].map((seconds) => ({
  time_control_seconds: seconds,
  increment_seconds: 0,
  label: `${seconds / 60} min`,
}))

export const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
export const AFTER_E4_FEN = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'

const files = 'abcdefgh'.split('')
export const OPENING_MOVES = [
  ...files.flatMap((f) => [`${f}2${f}3`, `${f}2${f}4`]),
  'b1a3',
  'b1c3',
  'g1f3',
  'g1h3',
]

/** An active game at the starting position, with alice as white. */
export function gameState(overrides: Partial<GameState> = {}): GameState {
  return {
    game_id: GAME_ID,
    status: 'active',
    version: 1,
    time_control_seconds: 300,
    increment_seconds: 0,
    players: { white: { id: 1, username: 'alice' }, black: { id: 2, username: 'bob' } },
    fen: START_FEN,
    turn: 'white',
    ply: 0,
    moves: [],
    last_move: null,
    is_check: false,
    legal_moves: OPENING_MOVES,
    captured: { white: [], black: [] },
    clocks: { white_ms: 300_000, black_ms: 300_000, running: 'white' },
    draw_offered_by: null,
    result: null,
    result_reason: null,
    created_at: '2026-02-01T10:00:00Z',
    started_at: '2026-02-01T10:00:01Z',
    finished_at: null,
    server_time: '2026-02-01T10:00:01Z',
    ...overrides,
  }
}

export function afterE4(): GameState {
  return gameState({
    version: 2,
    fen: AFTER_E4_FEN,
    turn: 'black',
    ply: 1,
    moves: [{ ply: 1, uci: 'e2e4', san: 'e4' }],
    last_move: 'e2e4',
    legal_moves: ['e7e5'],
    clocks: { white_ms: 297_000, black_ms: 300_000, running: 'black' },
  })
}

export function summary(index: number, overrides: Partial<GameSummary> = {}): GameSummary {
  return {
    game_id: `00000000-0000-0000-0000-${String(index).padStart(12, '0')}`,
    color: 'white',
    opponent: { id: 100 + index, username: `rival_${index}` },
    outcome: 'win',
    result: 'white_win',
    result_reason: 'checkmate',
    time_control_seconds: 300,
    increment_seconds: 0,
    move_count: 7,
    finished_at: '2026-02-02T10:00:00Z',
    ...overrides,
  }
}
