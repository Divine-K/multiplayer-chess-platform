import { motion, useReducedMotion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { isLightSquare, orientedSquares, parsePlacement } from '../game/chess'
import { PieceIcon } from '../game/board/PieceIcon'

/** A decorative replay of the Italian Game's first moves. It is an illustration, not a live game. */
const FRAMES: { fen: string; move: [string, string] | null }[] = [
  { fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR', move: null },
  { fen: 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR', move: ['e2', 'e4'] },
  { fen: 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR', move: ['e7', 'e5'] },
  { fen: 'rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R', move: ['g1', 'f3'] },
  { fen: 'r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R', move: ['b8', 'c6'] },
  { fen: 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R', move: ['f1', 'c4'] },
  { fen: 'r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R', move: ['f8', 'c5'] },
]
const FRAME_MS = 1600
const SQUARES = orientedSquares('white')

export function ShowcaseBoard() {
  const reducedMotion = useReducedMotion()
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (reducedMotion) return
    const timer = setInterval(() => setStep((s) => (s + 1) % (FRAMES.length + 2)), FRAME_MS)
    return () => clearInterval(timer)
  }, [reducedMotion])

  // The extra steps hold the final position before looping.
  const frame = FRAMES[reducedMotion ? FRAMES.length - 1 : Math.min(step, FRAMES.length - 1)]
  const pieces = parsePlacement(frame.fen)

  return (
    <div
      role="img"
      aria-label="Illustration of a chess opening"
      className="grid aspect-square w-full grid-cols-8 grid-rows-8 overflow-hidden rounded-xl border border-line-strong shadow-2xl shadow-black/50"
    >
      {SQUARES.map((square) => {
        const piece = pieces.get(square)
        const moved = frame.move?.[1] === square ? frame.move : null
        const highlighted = frame.move?.includes(square)
        return (
          <div key={square} className={`relative ${isLightSquare(square) ? 'bg-board-light' : 'bg-board-dark'}`}>
            {highlighted && <span className="absolute inset-0 bg-accent-400/35" />}
            {piece && (
              <motion.span
                key={moved ? `${frame.fen}:${square}` : square}
                className="absolute inset-[4%] z-10"
                initial={
                  moved
                    ? {
                        x: `${(moved[0].charCodeAt(0) - square.charCodeAt(0)) * 108}%`,
                        y: `${(Number(square[1]) - Number(moved[0][1])) * 108}%`,
                      }
                    : false
                }
                animate={{ x: 0, y: 0 }}
                transition={{ duration: 0.45, ease: 'easeInOut' }}
              >
                <PieceIcon type={piece.type} color={piece.color} />
              </motion.span>
            )}
          </div>
        )
      })}
    </div>
  )
}
