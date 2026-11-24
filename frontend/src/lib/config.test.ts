import { describe, expect, it } from 'vitest'
import { toWebSocketUrl } from './config'

describe('toWebSocketUrl', () => {
  it('maps http to ws', () => {
    expect(toWebSocketUrl('/ws/games/1', 'http://localhost:8000')).toBe('ws://localhost:8000/ws/games/1')
  })

  it('maps https to wss', () => {
    expect(toWebSocketUrl('/ws/games/1', 'https://api.example.com')).toBe('wss://api.example.com/ws/games/1')
  })
})
