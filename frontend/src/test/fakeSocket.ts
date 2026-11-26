import { act } from '@testing-library/react'
import { vi } from 'vitest'
import type { SocketLike } from '../features/game/session/gameSocket'
import { GAME_ID } from './fixtures'

/** A WebSocket the test controls from the server's side. */
export class FakeSocket implements SocketLike {
  static instances: FakeSocket[] = []

  readyState = 0
  sent: { type: string; payload: Record<string, unknown> }[] = []
  closedWith: number | null = null
  onopen: SocketLike['onopen'] = null
  onmessage: SocketLike['onmessage'] = null
  onclose: SocketLike['onclose'] = null
  readonly url: string

  constructor(url: string) {
    this.url = url
    FakeSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(JSON.parse(data))
  }

  close(code = 1000) {
    this.readyState = 3
    this.closedWith = code
  }

  /** Server side: accept the connection. */
  open() {
    act(() => {
      this.readyState = 1
      this.onopen?.()
    })
  }

  emit(type: string, payload: unknown) {
    act(() => this.onmessage?.({ data: JSON.stringify({ type, game_id: GAME_ID, payload }) }))
  }

  drop(code = 1006) {
    act(() => {
      this.readyState = 3
      this.onclose?.({ code })
    })
  }

  typesSent() {
    return this.sent.map((m) => m.type)
  }

  static latest(): FakeSocket {
    const socket = FakeSocket.instances.at(-1)
    if (!socket) throw new Error('No socket was opened')
    return socket
  }

  static install() {
    FakeSocket.instances = []
    vi.stubGlobal('WebSocket', FakeSocket)
  }
}
