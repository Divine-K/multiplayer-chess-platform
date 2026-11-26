import type { GameState } from '../../../lib/api/types'
import type { PlayerColor } from '../chess'
import type { BoardMove } from '../board/Board'
import type { ConnectionStatus, FatalReason } from './gameSocket'
import type { ServerMessage } from './messages'

export interface SessionState {
  game: GameState | null
  /** `performance.now()` when the clock values in `game` arrived; the countdown starts here. */
  clockReceivedAt: number
  color: PlayerColor | null
  opponentConnected: boolean
  connection: ConnectionStatus
  fatal: FatalReason | null
  pending: BoardMove | null
  /** True once this view has watched the game go from unfinished to over. */
  endedWhileWatching: boolean
}

export const initialSession: SessionState = {
  game: null,
  clockReceivedAt: 0,
  color: null,
  opponentConnected: false,
  connection: 'connecting',
  fatal: null,
  pending: null,
  endedWhileWatching: false,
}

export type SessionAction =
  | { type: 'server'; message: ServerMessage; receivedAt: number }
  | { type: 'status'; status: ConnectionStatus; fatal?: FatalReason }
  | { type: 'move_sent'; move: BoardMove }

export function isOver(game: GameState | null): boolean {
  return game?.status === 'finished' || game?.status === 'aborted'
}

/** Replaces the snapshot unless it is older than the one we already hold. */
function applySnapshot(session: SessionState, next: GameState, receivedAt: number): SessionState {
  const current = session.game
  if (current && next.version < current.version) return session
  return {
    ...session,
    game: next,
    clockReceivedAt: receivedAt,
    pending: current && next.version === current.version ? session.pending : null,
    endedWhileWatching: session.endedWhileWatching || (current !== null && !isOver(current) && isOver(next)),
  }
}

export function sessionReducer(session: SessionState, action: SessionAction): SessionState {
  if (action.type === 'move_sent') return { ...session, pending: action.move }
  if (action.type === 'status') {
    return {
      ...session,
      connection: action.status,
      fatal: action.fatal ?? null,
      // An unanswered move may or may not have arrived. The next snapshot settles it.
      pending: action.status === 'open' ? session.pending : null,
    }
  }

  const { message, receivedAt } = action
  switch (message.type) {
    case 'connected':
      return {
        ...applySnapshot(session, message.payload.state, receivedAt),
        color: message.payload.color,
        opponentConnected: message.payload.opponent_connected,
      }
    case 'player_connected':
    case 'player_disconnected':
      if (message.payload.color === session.color) return session
      return { ...session, opponentConnected: message.type === 'player_connected' }
    case 'game_started':
    case 'move_accepted':
    case 'draw_offered':
    case 'draw_declined':
    case 'game_finished':
    case 'state':
      return applySnapshot(session, message.payload.state, receivedAt)
    case 'move_rejected':
      return { ...applySnapshot(session, message.payload.state, receivedAt), pending: null }
    case 'clock_updated': {
      const { game } = session
      if (!game || message.payload.version !== game.version) return session
      return {
        ...session,
        game: { ...game, clocks: message.payload.clocks, server_time: message.payload.server_time },
        clockReceivedAt: receivedAt,
      }
    }
    case 'error':
      return { ...session, pending: null }
    default:
      return session
  }
}
