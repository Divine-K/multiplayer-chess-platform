import { describe, expect, it } from 'vitest'
import { formatClock, formatTimeControl, resultScore } from './format'

describe('formatting', () => {
  it.each([
    [600_000, '10:00'],
    [299_001, '5:00'],
    [61_000, '1:01'],
    [20_000, '0:20'],
    [19_999, '0:19.9'],
    [950, '0:00.9'],
    [0, '0:00.0'],
    [-50, '0:00.0'],
  ])('shows %i ms as %s', (ms, text) => {
    expect(formatClock(ms)).toBe(text)
  })

  it('formats time controls and scores', () => {
    expect(formatTimeControl(180, 2)).toBe('3+2')
    expect(resultScore('white_win')).toBe('1–0')
    expect(resultScore('draw')).toBe('½–½')
  })
})
