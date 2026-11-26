import { Handshake, Trophy, Flag, Ban } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { buttonStyles } from '../../components/ui/buttonStyles'
import { Modal } from '../../components/ui/Modal'
import type { GameState } from '../../lib/api/types'
import { resultScore } from '../../lib/format'
import type { PlayerColor } from './chess'
import { verdictFor } from './outcome'

interface ResultDialogProps {
  game: GameState
  viewer: PlayerColor
  onClose: () => void
  onNewGame: () => void
}

export function ResultDialog({ game, viewer, onClose, onNewGame }: ResultDialogProps) {
  const verdict = verdictFor(game, viewer)
  const Icon =
    game.status === 'aborted' ? Ban : game.result === 'draw' ? Handshake : verdict.title === 'You won' ? Trophy : Flag
  return (
    <Modal title={verdict.title} onClose={onClose}>
      <div className="mt-2 flex items-start gap-3">
        <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-accent-400" />
        <p className="text-ink-300">{verdict.detail}</p>
      </div>
      {game.result && <p className="mt-4 text-center font-display text-4xl font-semibold">{resultScore(game.result)}</p>}
      <div className="mt-6 grid gap-2">
        <Button onClick={onNewGame}>Find a new game</Button>
        <Button variant="secondary" onClick={onClose}>
          Review the board
        </Button>
        <Link to="/play" className={buttonStyles('ghost')}>
          Back to dashboard
        </Link>
      </div>
    </Modal>
  )
}
