import { X } from 'lucide-react'
import { Modal } from '../../../components/ui/Modal'
import { PIECE_NAMES, type PieceColor, type PromotionPiece } from '../chess'
import { PieceIcon } from './PieceIcon'

const CHOICES: PromotionPiece[] = ['q', 'r', 'b', 'n']

interface PromotionPickerProps {
  color: PieceColor
  square: string
  onSelect: (piece: PromotionPiece) => void
  onCancel: () => void
}

export function PromotionPicker({ color, square, onSelect, onCancel }: PromotionPickerProps) {
  return (
    <Modal title="Promote your pawn" onClose={onCancel}>
      <p className="mt-1 text-sm text-ink-500">Choose the piece for {square}.</p>
      <div className="mt-4 grid grid-cols-4 gap-2">
        {CHOICES.map((piece) => (
          <button
            key={piece}
            type="button"
            aria-label={PIECE_NAMES[piece]}
            onClick={() => onSelect(piece)}
            className="aspect-square rounded-lg bg-board-dark p-1 transition hover:bg-accent-500"
          >
            <PieceIcon type={piece} color={color} />
          </button>
        ))}
      </div>
      <button type="button" onClick={onCancel} className="mt-4 inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-100">
        <X aria-hidden="true" className="size-4" /> Cancel move
      </button>
    </Modal>
  )
}
