import { Avatar } from '../../components/ui/Avatar'
import type { GameState, Statistics } from '../../lib/api/types'
import { PieceIcon } from './board/PieceIcon'
import { PIECE_NAMES, PIECE_VALUES, materialLead, opposite, pieceColor, type PieceType, type PlayerColor } from './chess'
import { Clock } from './Clock'

interface PlayerBarProps {
  game: GameState
  color: PlayerColor
  isViewer: boolean
  /** `null` when presence is not meaningful (yourself, or a finished game). */
  online: boolean | null
  record: Statistics | null
  clockReceivedAt: number
}

function Captured({ game, color }: { game: GameState; color: PlayerColor }) {
  const pieces = [...game.captured[color]].sort((a, b) => PIECE_VALUES[a as PieceType] - PIECE_VALUES[b as PieceType])
  const lead = materialLead(game.captured) * (color === 'white' ? 1 : -1)
  const summary = pieces.length
    ? `Captured: ${pieces.map((p) => PIECE_NAMES[p as PieceType]).join(', ')}`
    : 'Nothing captured yet'
  return (
    <span className="flex h-5 items-center" role="img" aria-label={lead > 0 ? `${summary}. Ahead by ${lead}` : summary}>
      {/* The faint halo keeps black pieces visible against the dark background. */}
      {pieces.map((piece, index) => (
        <span
          key={index}
          className={`size-5 drop-shadow-[0_0_1px_rgb(236_239_244/0.8)] ${index > 0 && pieces[index - 1] === piece ? '-ml-2.5' : ''}`}
        >
          <PieceIcon type={piece as PieceType} color={pieceColor(opposite(color))} />
        </span>
      ))}
      {lead > 0 && <span className="ml-1.5 text-xs font-semibold text-ink-300">+{lead}</span>}
    </span>
  )
}

export function PlayerBar({ game, color, isViewer, online, record, clockReceivedAt }: PlayerBarProps) {
  const player = game.players[color]
  return (
    <div className="flex items-center gap-3" data-testid={`player-${color}`}>
      <span className="relative">
        <Avatar username={player.username} />
        {online !== null && (
          <span
            role="img"
            aria-label={online ? 'Connected' : 'Disconnected'}
            title={online ? 'Connected' : 'Disconnected'}
            className={`absolute -right-0.5 -bottom-0.5 size-3 rounded-full border-2 border-surface-950 ${online ? 'bg-ok' : 'bg-ink-500'}`}
          />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-sm">
          <span className="truncate font-semibold">{player.username}</span>
          {isViewer && <span className="text-ink-500">(you)</span>}
          <span className="inline-flex shrink-0 items-center gap-1.5 text-xs text-ink-500">
            <span aria-hidden="true" className={`size-2.5 rounded-[3px] border border-line-strong ${color === 'white' ? 'bg-ink-100' : 'bg-surface-950'}`} />
            {color === 'white' ? 'White' : 'Black'}
          </span>
          {record && (
            <span className="shrink-0 text-xs text-ink-500 max-sm:hidden">
              · {record.wins}W {record.losses}L {record.draws}D
            </span>
          )}
        </p>
        <Captured game={game} color={color} />
      </div>
      <Clock
        milliseconds={color === 'white' ? game.clocks.white_ms : game.clocks.black_ms}
        running={game.clocks.running === color}
        receivedAt={clockReceivedAt}
        label={`${player.username}'s clock`}
      />
    </div>
  )
}
