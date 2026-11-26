import { motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  PIECE_NAMES,
  findKing,
  isLightSquare,
  isPromotionMove,
  orientedSquares,
  parsePlacement,
  pieceColor,
  targetsFrom,
  type PlayerColor,
  type PromotionPiece,
} from '../chess'
import { PieceIcon } from './PieceIcon'
import { PromotionPicker } from './PromotionPicker'

export interface BoardMove {
  from: string
  to: string
  promotion?: PromotionPiece
}

interface BoardProps {
  fen: string
  orientation: PlayerColor
  /** Whose pieces this viewer may move. */
  playerColor: PlayerColor | null
  /** From the server. Used for highlighting only; the server validates every move again. */
  legalMoves: string[]
  lastMove: string | null
  checkedColor: PlayerColor | null
  interactive: boolean
  /** A move that has been sent and not yet answered. The pieces do not move until it is. */
  pending: BoardMove | null
  onMove: (move: BoardMove) => void
}

interface Drag {
  from: string
  startX: number
  startY: number
  x: number
  y: number
  size: number
  active: boolean
}

const DRAG_THRESHOLD_PX = 5

function squareAt(x: number, y: number): string | null {
  const element = document.elementFromPoint?.(x, y)
  return element?.closest<HTMLElement>('[data-square]')?.dataset.square ?? null
}

/** Offset, in squares, from where a piece landed back to where it came from. */
function travel(from: string, to: string, orientation: PlayerColor) {
  const sign = orientation === 'white' ? 1 : -1
  return {
    x: `${(from.charCodeAt(0) - to.charCodeAt(0)) * 100 * sign}%`,
    y: `${(Number(to[1]) - Number(from[1])) * 100 * sign}%`,
  }
}

export function Board(props: BoardProps) {
  const { fen, orientation, playerColor, legalMoves, lastMove, checkedColor, interactive, pending, onMove } = props
  const pieces = useMemo(() => parsePlacement(fen), [fen])
  const squares = useMemo(() => orientedSquares(orientation), [orientation])

  // Selection and promotion belong to one position: a new position silently discards them.
  const [selection, setSelection] = useState<{ fen: string; square: string } | null>(null)
  const [promotion, setPromotion] = useState<{ fen: string; from: string; to: string } | null>(null)
  const selected = interactive && selection?.fen === fen ? selection.square : null
  const promoting = interactive && promotion?.fen === fen ? promotion : null
  const targets = useMemo(
    () => (selected ? targetsFrom(legalMoves, selected) : new Set<string>()),
    [legalMoves, selected],
  )

  const [drag, setDrag] = useState<Drag | null>(null)
  const suppressClick = useRef(false)
  const [focused, setFocused] = useState<string | null>(null)
  const grid = useRef<HTMLDivElement>(null)

  const checkedSquare = checkedColor ? findKing(pieces, pieceColor(checkedColor)) : null

  function isOwnPiece(square: string): boolean {
    const piece = pieces.get(square)
    return Boolean(piece && playerColor && piece.color === pieceColor(playerColor))
  }

  function attempt(from: string, to: string) {
    setSelection(null)
    if (isPromotionMove(legalMoves, from, to)) setPromotion({ fen, from, to })
    else onMove({ from, to })
  }

  function handleClick(square: string) {
    if (suppressClick.current) {
      suppressClick.current = false
      return
    }
    if (!interactive) return
    if (selected && targets.has(square)) attempt(selected, square)
    else if (isOwnPiece(square) && square !== selected) setSelection({ fen, square })
    else setSelection(null)
  }

  function handlePointerDown(square: string, event: React.PointerEvent<HTMLButtonElement>) {
    suppressClick.current = false
    if (!interactive || event.button !== 0 || !isOwnPiece(square)) return
    const size = event.currentTarget.getBoundingClientRect().width
    setDrag({
      from: square,
      startX: event.clientX,
      startY: event.clientY,
      x: event.clientX,
      y: event.clientY,
      size,
      active: false,
    })
  }

  const dragRef = useRef(drag)
  const attemptRef = useRef(attempt)
  const targetsFor = useRef((from: string) => targetsFrom(legalMoves, from))
  useEffect(() => {
    dragRef.current = drag
    attemptRef.current = attempt
    targetsFor.current = (from: string) => targetsFrom(legalMoves, from)
  })

  const dragging = drag !== null
  useEffect(() => {
    if (!dragging) return

    function handleMove(event: PointerEvent) {
      const current = dragRef.current
      if (!current) return
      const distance = Math.hypot(event.clientX - current.startX, event.clientY - current.startY)
      if (!current.active && distance < DRAG_THRESHOLD_PX) return
      if (!current.active) setSelection({ fen, square: current.from })
      const next = { ...current, x: event.clientX, y: event.clientY, active: true }
      dragRef.current = next
      setDrag(next)
    }

    function handleUp(event: PointerEvent) {
      const current = dragRef.current
      dragRef.current = null
      setDrag(null)
      if (!current?.active) return // a plain click: the click handler deals with it
      suppressClick.current = true
      const target = squareAt(event.clientX, event.clientY)
      if (target && targetsFor.current(current.from).has(target)) attemptRef.current(current.from, target)
      else if (target !== current.from) setSelection(null)
    }

    function handleCancel() {
      dragRef.current = null
      setDrag(null)
    }

    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
    window.addEventListener('pointercancel', handleCancel)
    return () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
      window.removeEventListener('pointercancel', handleCancel)
    }
  }, [dragging, fen])

  function handleKeyDown(event: React.KeyboardEvent, index: number) {
    if (event.key === 'Escape') setSelection(null)
    const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -8, ArrowDown: 8 }[event.key]
    if (step === undefined) return
    event.preventDefault()
    const next = index + step
    const leavesRow = Math.abs(step) === 1 && Math.floor(next / 8) !== Math.floor(index / 8)
    if (next < 0 || next > 63 || leavesRow) return
    setFocused(squares[next])
    grid.current?.querySelector<HTMLElement>(`[data-square="${squares[next]}"]`)?.focus()
  }

  // One square at a time is in the tab order; arrow keys move between them.
  const tabStop = focused ?? squares[52]
  const draggedPiece = drag?.active ? pieces.get(drag.from) : undefined

  return (
    <div className="relative aspect-square w-full select-none">
      <div
        ref={grid}
        role="group"
        aria-label={`Chessboard, ${orientation} at the bottom`}
        className="grid size-full grid-cols-8 grid-rows-8 overflow-hidden rounded-lg border border-line-strong"
      >
        {squares.map((square, index) => {
          const piece = pieces.get(square)
          const light = isLightSquare(square)
          const isTarget = targets.has(square)
          const isLast = lastMove !== null && (lastMove.slice(0, 2) === square || lastMove.slice(2, 4) === square)
          const isPending = pending !== null && (pending.from === square || pending.to === square)
          const arrived = lastMove !== null && lastMove.slice(2, 4) === square
          const movable = interactive && isOwnPiece(square)
          const description = piece ? `${piece.color === 'w' ? 'white' : 'black'} ${PIECE_NAMES[piece.type]}` : 'empty'
          return (
            <button
              key={square}
              type="button"
              data-square={square}
              data-selected={selected === square || undefined}
              data-target={isTarget || undefined}
              data-last-move={isLast || undefined}
              data-check={checkedSquare === square || undefined}
              data-pending={isPending || undefined}
              aria-label={`${square}, ${description}${isTarget ? ', legal move' : ''}${checkedSquare === square ? ', in check' : ''}`}
              aria-pressed={selected === square}
              tabIndex={square === tabStop ? 0 : -1}
              onFocus={() => setFocused(square)}
              onClick={() => handleClick(square)}
              onPointerDown={(event) => handlePointerDown(square, event)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              onDragStart={(event) => event.preventDefault()}
              className={`relative focus-visible:z-10 focus-visible:-outline-offset-2 ${light ? 'bg-board-light' : 'bg-board-dark'} ${movable ? 'cursor-grab touch-none' : isTarget ? 'cursor-pointer' : 'cursor-default'}`}
            >
              {isLast && <span aria-hidden="true" className="absolute inset-0 bg-accent-400/35" />}
              {selected === square && <span aria-hidden="true" className="absolute inset-0 bg-accent-500/60" />}
              {isPending && <span aria-hidden="true" className="absolute inset-0 animate-pulse bg-accent-400/50" />}
              {checkedSquare === square && (
                <span aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle,rgb(214_62_62/0.9)_20%,rgb(214_62_62/0.15)_72%)]" />
              )}
              {index % 8 === 0 && (
                <span aria-hidden="true" className={`absolute top-0.5 left-1 text-[10px] font-semibold ${light ? 'text-board-dark' : 'text-board-light'}`}>
                  {square[1]}
                </span>
              )}
              {index >= 56 && (
                <span aria-hidden="true" className={`absolute right-1 bottom-0 text-[10px] font-semibold ${light ? 'text-board-dark' : 'text-board-light'}`}>
                  {square[0]}
                </span>
              )}
              {piece && (
                <motion.span
                  // Remount when a move lands here so the piece slides in from its origin.
                  key={arrived ? `${fen}:${square}` : square}
                  initial={arrived ? travel(lastMove.slice(0, 2), square, orientation) : false}
                  animate={{ x: 0, y: 0 }}
                  transition={{ duration: 0.18, ease: 'easeOut' }}
                  className={`pointer-events-none absolute inset-[3%] z-10 ${drag?.active && drag.from === square ? 'opacity-30' : ''}`}
                >
                  <PieceIcon type={piece.type} color={piece.color} />
                </motion.span>
              )}
              {isTarget && (
                <span aria-hidden="true" className={`pointer-events-none absolute z-20 rounded-full ${piece ? 'inset-0 border-[5px] border-surface-950/35' : 'inset-[36%] bg-surface-950/35'}`} />
              )}
            </button>
          )
        })}
      </div>

      {drag?.active && draggedPiece && (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed z-50 drop-shadow-xl"
          style={{ width: drag.size, height: drag.size, left: drag.x - drag.size / 2, top: drag.y - drag.size / 2 }}
        >
          <PieceIcon type={draggedPiece.type} color={draggedPiece.color} />
        </div>
      )}

      {promoting && playerColor && (
        <PromotionPicker
          color={pieceColor(playerColor)}
          square={promoting.to}
          onCancel={() => setPromotion(null)}
          onSelect={(piece) => {
            setPromotion(null)
            onMove({ from: promoting.from, to: promoting.to, promotion: piece })
          }}
        />
      )}
    </div>
  )
}
