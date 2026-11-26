import { describe, expect, it } from 'vitest'
import { afterE4, gameState } from '../../../test/fixtures'
import { initialSession, sessionReducer, type SessionState } from './gameReducer'
import type { ServerMessage } from './messages'

const receive = (state: SessionState, type: string, payload: unknown, receivedAt = 1) =>
  sessionReducer(state, {
    type: 'server',
    message: { type, game_id: 'g', payload } as ServerMessage,
    receivedAt,
  })

const connected = receive(initialSession, 'connected', {
  color: 'white',
  opponent_connected: false,
  state: gameState(),
})

describe('sessionReducer', () => {
  it('adopts the first snapshot', () => {
    expect(connected.color).toBe('white')
    expect(connected.game?.version).toBe(1)
    expect(connected.opponentConnected).toBe(false)
  })

  it('ignores a snapshot older than the one held', () => {
    const newer = receive(connected, 'move_accepted', { state: afterE4() })
    expect(receive(newer, 'state', { state: gameState() })).toBe(newer)
  })

  it('tracks only the opponent’s presence', () => {
    expect(receive(connected, 'player_connected', { color: 'black' }).opponentConnected).toBe(true)
    expect(receive(connected, 'player_connected', { color: 'white' }).opponentConnected).toBe(false)
  })

  it('re-bases the clocks only for the current version', () => {
    const clocks = { white_ms: 250_000, black_ms: 300_000, running: 'white' }
    const synced = receive(connected, 'clock_updated', { clocks, version: 1, server_time: 'later' }, 99)
    expect(synced.game?.clocks).toEqual(clocks)
    expect(synced.clockReceivedAt).toBe(99)
    expect(receive(connected, 'clock_updated', { clocks, version: 7, server_time: 'x' })).toBe(connected)
  })

  it('clears a pending move on an answer or a lost connection', () => {
    const sent = sessionReducer(connected, { type: 'move_sent', move: { from: 'e2', to: 'e4' } })
    expect(receive(sent, 'state', { state: gameState() }).pending).not.toBeNull() // same version: still unanswered
    expect(receive(sent, 'move_accepted', { state: afterE4() }).pending).toBeNull()
    expect(receive(sent, 'move_rejected', { state: gameState(), code: 'x', message: 'x' }).pending).toBeNull()
    expect(receive(sent, 'error', { code: 'x', message: 'x' }).pending).toBeNull()
    expect(sessionReducer(sent, { type: 'status', status: 'reconnecting' }).pending).toBeNull()
  })

  it('notices a game ending while it is being watched, but not one that was already over', () => {
    const finished = gameState({ status: 'finished', version: 3, result: 'draw', result_reason: 'stalemate' })
    expect(receive(connected, 'game_finished', { state: finished }).endedWhileWatching).toBe(true)
    const opened = receive(initialSession, 'connected', {
      color: 'white',
      opponent_connected: false,
      state: finished,
    })
    expect(opened.endedWhileWatching).toBe(false)
  })
})
