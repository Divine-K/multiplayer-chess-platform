import type { GameResult, ResultReason } from './api/types'

/** Chess-clock display: m:ss, with tenths in the last twenty seconds. */
export function formatClock(milliseconds: number): string {
  const ms = Math.max(0, milliseconds)
  if (ms < 20_000) {
    const tenths = Math.floor(ms / 100)
    return `0:${String(Math.floor(tenths / 10)).padStart(2, '0')}.${tenths % 10}`
  }
  const seconds = Math.ceil(ms / 1000)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function formatTimeControl(seconds: number, increment: number): string {
  return `${Math.round(seconds / 60)}+${increment}`
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(
    new Date(iso),
  )
}

const REASONS: Record<ResultReason, string> = {
  checkmate: 'by checkmate',
  stalemate: 'by stalemate',
  insufficient_material: 'by insufficient material',
  threefold_repetition: 'by threefold repetition',
  fifty_move_rule: 'by the fifty-move rule',
  resignation: 'by resignation',
  timeout: 'on time',
  timeout_vs_insufficient_material: 'on time, with no mating material left',
  draw_agreement: 'by agreement',
  never_started: 'the game never started',
}

export function describeReason(reason: ResultReason): string {
  return REASONS[reason]
}

export function resultScore(result: GameResult): string {
  if (result === 'white_win') return '1–0'
  if (result === 'black_win') return '0–1'
  return '½–½'
}
