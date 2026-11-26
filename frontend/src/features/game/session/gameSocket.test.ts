import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FakeSocket } from '../../../test/fakeSocket'
import { GameSocket, PING_INTERVAL_MS, SILENCE_LIMIT_MS, type ConnectionStatus, type FatalReason } from './gameSocket'

describe('GameSocket', () => {
  let statuses: [ConnectionStatus, FatalReason?][]
  let over: boolean
  let token: string | null

  function connect() {
    const connection = new GameSocket({
      url: 'ws://api.test/ws/games/abc',
      getToken: () => token,
      onMessage: () => {},
      onStatus: (status, fatal) => statuses.push(fatal ? [status, fatal] : [status]),
      shouldReconnect: () => !over,
      createSocket: (url) => new FakeSocket(url),
    })
    connection.start()
    return connection
  }

  function authenticate() {
    FakeSocket.latest().open()
    FakeSocket.latest().emit('connected', {})
  }

  beforeEach(() => {
    vi.useFakeTimers()
    FakeSocket.instances = []
    statuses = []
    over = false
    token = 'secret-token'
  })

  it('authenticates in the first message, never in the URL', () => {
    connect()
    const socket = FakeSocket.latest()
    socket.open()
    expect(socket.url).not.toContain('secret-token')
    expect(socket.sent).toEqual([{ type: 'auth', payload: { token: 'secret-token' } }])
    expect(statuses).toEqual([['connecting']])
    socket.emit('connected', {})
    expect(statuses.at(-1)).toEqual(['open'])
  })

  it('refuses to send before the server has accepted it', () => {
    const connection = connect()
    FakeSocket.latest().open()
    expect(connection.send('resign')).toBe(false)
    FakeSocket.latest().emit('connected', {})
    expect(connection.send('resign')).toBe(true)
  })

  it('sends heartbeats', () => {
    connect()
    authenticate()
    vi.advanceTimersByTime(PING_INTERVAL_MS + 1000)
    expect(FakeSocket.latest().typesSent()).toEqual(['auth', 'ping'])
  })

  it('pings from incoming traffic, which still arrives when timers are throttled', () => {
    connect()
    authenticate()
    vi.setSystemTime(Date.now() + PING_INTERVAL_MS + 1)
    FakeSocket.latest().emit('clock_updated', {})
    expect(FakeSocket.latest().typesSent()).toContain('ping')
  })

  it('acts on an announced close at once, without waiting for the close frame', () => {
    connect()
    authenticate()
    const socket = FakeSocket.latest()
    socket.emit('closing', { code: 4409 })
    expect(statuses.at(-1)).toEqual(['closed', 'replaced'])
    expect(socket.closedWith).toBe(1000)
    vi.advanceTimersByTime(60_000)
    expect(FakeSocket.instances).toHaveLength(1)
  })

  it('reconnects only once after an announced non-fatal close', () => {
    connect()
    authenticate()
    const socket = FakeSocket.latest()
    socket.emit('closing', { code: 4410 })
    expect(statuses.at(-1)).toEqual(['reconnecting'])
    socket.drop(1006) // the close frame or its absence arriving later changes nothing
    vi.advanceTimersByTime(500)
    expect(FakeSocket.instances).toHaveLength(2)
  })

  it('reconnects with growing delays and resets them after success', () => {
    connect()
    authenticate()
    FakeSocket.latest().drop(1006)
    expect(statuses.at(-1)).toEqual(['reconnecting'])
    vi.advanceTimersByTime(499)
    expect(FakeSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(FakeSocket.instances).toHaveLength(2)

    FakeSocket.latest().drop(1006)
    vi.advanceTimersByTime(999)
    expect(FakeSocket.instances).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(FakeSocket.instances).toHaveLength(3)

    authenticate()
    FakeSocket.latest().drop(1012)
    vi.advanceTimersByTime(500)
    expect(FakeSocket.instances).toHaveLength(4)
  })

  it.each([
    [4401, 'unauthorized'],
    [4403, 'forbidden'],
    [4404, 'not_found'],
    [4409, 'replaced'],
    [4400, 'protocol'],
    [1009, 'protocol'],
  ])('gives up after close code %i', (code, reason) => {
    connect()
    authenticate()
    FakeSocket.latest().drop(code)
    vi.advanceTimersByTime(60_000)
    expect(FakeSocket.instances).toHaveLength(1)
    expect(statuses.at(-1)).toEqual(['closed', reason])
  })

  it.each([4408, 4410, 4429])('retries after close code %i', (code) => {
    connect()
    FakeSocket.latest().drop(code)
    vi.advanceTimersByTime(500)
    expect(FakeSocket.instances).toHaveLength(2)
  })

  it('replaces a connection that has gone silent', () => {
    connect()
    authenticate()
    const first = FakeSocket.latest()
    vi.advanceTimersByTime(SILENCE_LIMIT_MS + 2000)
    expect(first.closedWith).not.toBeNull()
    expect(FakeSocket.instances.length).toBeGreaterThan(1)
  })

  it('does not reconnect once the game is over', () => {
    connect()
    authenticate()
    over = true
    FakeSocket.latest().drop(1006)
    vi.advanceTimersByTime(60_000)
    expect(FakeSocket.instances).toHaveLength(1)
    expect(statuses.at(-1)).toEqual(['closed'])
  })

  it('does not connect without a token', () => {
    token = null
    connect()
    FakeSocket.latest().open()
    expect(FakeSocket.latest().sent).toEqual([])
    expect(statuses.at(-1)).toEqual(['closed', 'unauthorized'])
  })

  it('stays closed after stop, including a pending retry', () => {
    const connection = connect()
    FakeSocket.latest().drop(1006)
    connection.stop()
    vi.advanceTimersByTime(60_000)
    expect(FakeSocket.instances).toHaveLength(1)
  })
})
