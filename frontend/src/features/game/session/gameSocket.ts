/**
 * The connection to one game's WebSocket: authentication, heartbeat and reconnection.
 * Framework-free so that its policy can be tested directly. See docs/WEBSOCKET_PROTOCOL.md.
 */
import type { ServerMessage } from './messages'

export const PING_INTERVAL_MS = 20_000
/** The server sends something at least every 20 s (a pong), so longer silence means a dead link. */
export const SILENCE_LIMIT_MS = 45_000
export const RECONNECT_DELAYS_MS = [500, 1000, 2000, 4000, 8000]

export type ConnectionStatus = 'connecting' | 'open' | 'reconnecting' | 'closed'

/** Close codes after which retrying would be wrong. */
export type FatalReason = 'unauthorized' | 'forbidden' | 'not_found' | 'replaced' | 'protocol'

const FATAL_CODES: Record<number, FatalReason> = {
  1009: 'protocol',
  4400: 'protocol',
  4401: 'unauthorized',
  4403: 'forbidden',
  4404: 'not_found',
  4409: 'replaced',
}

export interface SocketLike {
  readyState: number
  onopen: (() => void) | null
  onmessage: ((event: { data: unknown }) => void) | null
  onclose: ((event: { code: number }) => void) | null
  send(data: string): void
  close(code?: number): void
}

export interface GameSocketOptions {
  url: string
  getToken: () => string | null
  onMessage: (message: ServerMessage) => void
  onStatus: (status: ConnectionStatus, fatal?: FatalReason) => void
  /** Return false once there is nothing left to reconnect for (the game is over). */
  shouldReconnect?: () => boolean
  createSocket?: (url: string) => SocketLike
}

const OPEN = 1

export class GameSocket {
  private socket: SocketLike | null = null
  private attempts = 0
  private stopped = true
  private authenticated = false
  private lastPingAt = 0
  private lastMessageAt = 0
  private heartbeat: ReturnType<typeof setInterval> | undefined
  private retry: ReturnType<typeof setTimeout> | undefined

  private readonly options: GameSocketOptions

  constructor(options: GameSocketOptions) {
    this.options = options
  }

  start(): void {
    this.stop()
    this.stopped = false
    this.attempts = 0
    this.options.onStatus('connecting')
    this.open()
  }

  stop(): void {
    this.stopped = true
    clearTimeout(this.retry)
    this.discard()
  }

  /** Returns false when the message could not be sent because there is no live connection. */
  send(type: string, payload: Record<string, unknown> = {}): boolean {
    if (!this.authenticated || this.socket?.readyState !== OPEN) return false
    this.socket.send(JSON.stringify({ type, payload }))
    return true
  }

  private open(): void {
    const create = this.options.createSocket ?? ((url: string) => new WebSocket(url) as unknown as SocketLike)
    const socket = create(this.options.url)
    this.socket = socket
    this.lastMessageAt = Date.now()

    socket.onopen = () => {
      const token = this.options.getToken()
      if (!token) {
        this.fail('unauthorized')
        return
      }
      // The token travels in the first message, never in the URL.
      socket.send(JSON.stringify({ type: 'auth', payload: { token } }))
    }
    socket.onmessage = (event) => this.receive(event.data)
    socket.onclose = (event) => this.handleClose(event.code)

    this.heartbeat = setInterval(() => this.beat(), 1000)
  }

  private receive(data: unknown): void {
    let message: ServerMessage
    try {
      message = JSON.parse(String(data)) as ServerMessage
    } catch {
      return
    }
    this.lastMessageAt = Date.now()
    if (message.type === 'closing') {
      // Act on the announced reason now: a proxy may lose or delay the close frame that follows.
      this.handleClose(message.payload.code)
      return
    }
    if (message.type === 'connected') {
      this.authenticated = true
      this.attempts = 0
      this.lastPingAt = Date.now()
      this.options.onStatus('open')
    }
    this.options.onMessage(message)
    // Background tabs throttle timers, so incoming traffic also drives the heartbeat.
    this.pingIfDue()
  }

  private beat(): void {
    if (Date.now() - this.lastMessageAt > SILENCE_LIMIT_MS) {
      this.handleClose(1006)
      return
    }
    this.pingIfDue()
  }

  private pingIfDue(): void {
    if (Date.now() - this.lastPingAt < PING_INTERVAL_MS) return
    if (this.send('ping')) this.lastPingAt = Date.now()
  }

  private discard(): void {
    clearInterval(this.heartbeat)
    this.authenticated = false
    const socket = this.socket
    this.socket = null
    if (!socket) return
    socket.onopen = null
    socket.onmessage = null
    socket.onclose = null
    socket.close(1000)
  }

  private fail(reason: FatalReason): void {
    this.stop()
    this.options.onStatus('closed', reason)
  }

  private handleClose(code: number): void {
    if (this.stopped) return
    const fatal = FATAL_CODES[code]
    if (fatal) {
      this.fail(fatal)
      return
    }
    this.discard()
    if (this.options.shouldReconnect?.() === false) {
      this.stopped = true
      this.options.onStatus('closed')
      return
    }
    const delay = RECONNECT_DELAYS_MS[Math.min(this.attempts, RECONNECT_DELAYS_MS.length - 1)]
    this.attempts += 1
    this.options.onStatus('reconnecting')
    this.retry = setTimeout(() => this.open(), delay)
  }
}
