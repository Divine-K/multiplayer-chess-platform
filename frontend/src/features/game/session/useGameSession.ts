import { useCallback, useEffect, useReducer, useRef } from 'react'
import { useToast } from '../../../components/ui/toastContext'
import { toWebSocketUrl } from '../../../lib/config'
import { tokenStorage } from '../../../lib/tokenStorage'
import type { BoardMove } from '../board/Board'
import { initialSession, isOver, sessionReducer, type SessionAction, type SessionState } from './gameReducer'
import { GameSocket } from './gameSocket'

export interface GameSession extends SessionState {
  sendMove: (move: BoardMove) => void
  resign: () => void
  offerDraw: () => void
  respondToDraw: (accept: boolean) => void
  reconnect: () => void
}

/** Live, server-authoritative state for one game. Mount with a `key` of the game id. */
export function useGameSession(gameId: string): GameSession {
  const toast = useToast()
  const [session, dispatch] = useReducer(sessionReducer, initialSession)
  const socket = useRef<GameSocket | null>(null)

  useEffect(() => {
    // Mirrors the reducer synchronously, so message handlers can see the state they apply to.
    let latest = initialSession
    function apply(action: SessionAction) {
      latest = sessionReducer(latest, action)
      dispatch(action)
    }

    const connection = new GameSocket({
      url: toWebSocketUrl(`/ws/games/${encodeURIComponent(gameId)}`),
      getToken: () => tokenStorage.get(),
      shouldReconnect: () => !isOver(latest.game),
      onStatus: (status, fatal) => apply({ type: 'status', status, fatal }),
      onMessage: (message) => {
        const before = latest
        apply({ type: 'server', message, receivedAt: performance.now() })
        if (message.type === 'move_rejected') toast(message.payload.message, 'error')
        if (message.type === 'error') toast(message.payload.message, 'error')
        if (message.type === 'draw_declined' && before.game?.draw_offered_by === before.color) {
          toast('Your draw offer was declined.')
        }
        // A clock sync for a newer version means we missed an event: ask for the whole state.
        if (message.type === 'clock_updated' && latest.game && message.payload.version > latest.game.version) {
          connection.send('sync')
        }
      },
    })
    socket.current = connection
    connection.start()
    return () => {
      connection.stop()
      socket.current = null
    }
  }, [gameId, toast])

  const command = useCallback(
    (type: string, payload?: Record<string, unknown>) => {
      const sent = socket.current?.send(type, payload) ?? false
      if (!sent) toast('Not connected. Try again once the connection is back.', 'error')
      return sent
    },
    [toast],
  )

  const sendMove = useCallback(
    (move: BoardMove) => {
      if (command('move', { ...move })) dispatch({ type: 'move_sent', move })
    },
    [command],
  )
  const resign = useCallback(() => void command('resign'), [command])
  const offerDraw = useCallback(() => void command('offer_draw'), [command])
  const respondToDraw = useCallback(
    (accept: boolean) => void command(accept ? 'accept_draw' : 'decline_draw'),
    [command],
  )
  const reconnect = useCallback(() => socket.current?.start(), [])

  return { ...session, sendMove, resign, offerDraw, respondToDraw, reconnect }
}
