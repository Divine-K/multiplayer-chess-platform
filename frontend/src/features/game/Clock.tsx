import { useEffect, useState } from 'react'
import { formatClock } from '../../lib/format'

const TICK_MS = 100

interface ClockProps {
  /** Time left when the server's snapshot arrived. */
  milliseconds: number
  running: boolean
  receivedAt: number
  label: string
}

/**
 * Animates the server's clock between updates. It is a display only: the server decides when a
 * flag falls, and every server message re-bases this countdown.
 */
export function Clock({ milliseconds, running, receivedAt, label }: ClockProps) {
  const [now, setNow] = useState(() => performance.now())

  useEffect(() => {
    if (!running) return
    const timer = setInterval(() => setNow(performance.now()), TICK_MS)
    return () => clearInterval(timer)
  }, [running])

  const remaining = Math.max(0, running ? milliseconds - Math.max(0, now - receivedAt) : milliseconds)
  const urgent = running && remaining < 20_000

  return (
    <div
      role="timer"
      aria-label={label}
      data-running={running || undefined}
      className={`min-w-24 rounded-lg border px-3 py-1.5 text-right font-mono text-2xl font-semibold tabular-nums transition-colors ${
        urgent
          ? 'border-danger bg-danger/15 text-danger'
          : running
            ? 'border-accent-400 bg-ink-100 text-surface-950'
            : 'border-line bg-surface-900 text-ink-300'
      }`}
    >
      {formatClock(remaining)}
    </div>
  )
}
