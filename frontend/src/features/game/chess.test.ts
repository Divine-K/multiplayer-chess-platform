import { describe, expect, it } from 'vitest'
import { START_FEN } from '../../test/fixtures'
import { isLightSquare, isPromotionMove, materialLead, orientedSquares, parsePlacement, targetsFrom } from './chess'

describe('board helpers', () => {
  it('reads piece placement from a FEN', () => {
    const board = parsePlacement(START_FEN)
    expect(board.size).toBe(32)
    expect(board.get('a1')).toEqual({ type: 'r', color: 'w' })
    expect(board.get('g8')).toEqual({ type: 'n', color: 'b' })
    expect(board.has('e4')).toBe(false)
  })

  it('orders squares from each player’s point of view', () => {
    expect(orientedSquares('white').slice(0, 2)).toEqual(['a8', 'b8'])
    expect(orientedSquares('black').slice(0, 2)).toEqual(['h1', 'g1'])
  })

  it('colours the squares like a real board', () => {
    expect(isLightSquare('a1')).toBe(false)
    expect(isLightSquare('h1')).toBe(true)
    expect(isLightSquare('d1')).toBe(true)
  })

  it('derives destinations and promotions from the server’s move list', () => {
    expect([...targetsFrom(['e2e3', 'e2e4', 'd2d4'], 'e2')]).toEqual(['e3', 'e4'])
    expect(isPromotionMove(['a7a8q', 'a7a8n'], 'a7', 'a8')).toBe(true)
    expect(isPromotionMove(['a2a3'], 'a2', 'a3')).toBe(false)
  })

  it('computes the material lead', () => {
    expect(materialLead({ white: ['q'], black: ['r', 'p'] })).toBe(3)
  })
})
