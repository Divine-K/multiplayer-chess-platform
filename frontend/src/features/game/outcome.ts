import type { GameState } from '../../lib/api/types'
import { describeReason } from '../../lib/format'
import type { PlayerColor } from './chess'

export interface Verdict {
  title: string
  detail: string
}

/** Words the server's result from the viewer's side of the board. */
export function verdictFor(game: GameState, viewer: PlayerColor): Verdict {
  if (game.status === 'aborted') {
    return { title: 'Game cancelled', detail: 'It ended before it started, so no result was recorded.' }
  }
  const reason = game.result_reason ? describeReason(game.result_reason) : ''
  if (game.result === 'draw') return { title: 'Draw', detail: `The game was drawn ${reason}.` }
  const winner: PlayerColor = game.result === 'white_win' ? 'white' : 'black'
  return winner === viewer
    ? { title: 'You won', detail: `You won ${reason}.` }
    : { title: 'You lost', detail: `${game.players[winner].username} won ${reason}.` }
}
