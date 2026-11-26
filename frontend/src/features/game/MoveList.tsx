import { useEffect, useRef } from 'react'
import type { MoveInfo } from '../../lib/api/types'

export function MoveList({ moves }: { moves: MoveInfo[] }) {
  const container = useRef<HTMLDivElement>(null)

  // Keep the latest move in view without scrolling the page.
  useEffect(() => {
    if (container.current) container.current.scrollTop = container.current.scrollHeight
  }, [moves.length])

  const turns = Array.from({ length: Math.ceil(moves.length / 2) }, (_, i) => moves.slice(i * 2, i * 2 + 2))

  return (
    <div ref={container} className="max-h-56 min-h-32 overflow-y-auto lg:max-h-80" tabIndex={0} aria-label="Move history" role="region">
      {turns.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-ink-500">No moves yet.</p>
      ) : (
        <ol className="text-sm">
          {turns.map(([white, black], index) => (
            <li key={white.ply} className="grid grid-cols-[3rem_1fr_1fr] px-4 py-1.5 odd:bg-surface-800/60">
              <span className="text-ink-500 tabular-nums">{index + 1}.</span>
              {[white, black].map(
                (move) =>
                  move && (
                    <span key={move.ply} className={`font-mono ${move.ply === moves.length ? 'font-semibold text-accent-300' : ''}`}>
                      {move.san}
                    </span>
                  ),
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
