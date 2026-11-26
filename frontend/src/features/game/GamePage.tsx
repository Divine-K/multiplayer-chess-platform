import { motion } from 'framer-motion'
import { Flag, Handshake, WifiOff } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { buttonStyles } from '../../components/ui/buttonStyles'
import { Modal } from '../../components/ui/Modal'
import { Skeleton } from '../../components/ui/Skeleton'
import { Spinner } from '../../components/ui/Spinner'
import { gamesApi } from '../../lib/api/games'
import type { GameState } from '../../lib/api/types'
import { formatTimeControl, resultScore } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useAuth } from '../auth/authContext'
import { useMatchmaking } from '../matchmaking/matchmakingContext'
import { Board } from './board/Board'
import { opposite, type PlayerColor } from './chess'
import { MoveList } from './MoveList'
import { verdictFor } from './outcome'
import { PlayerBar } from './PlayerBar'
import { ResultDialog } from './ResultDialog'
import { isOver } from './session/gameReducer'
import type { FatalReason } from './session/gameSocket'
import { useGameSession, type GameSession } from './session/useGameSession'

const FATAL_MESSAGES: Record<FatalReason, { title: string; detail: string }> = {
  unauthorized: { title: 'Please sign in again', detail: 'Your session is no longer valid.' },
  forbidden: { title: 'This is not your game', detail: 'Only its two players can open it.' },
  not_found: { title: 'Game not found', detail: 'The link may be wrong, or the game no longer exists.' },
  replaced: {
    title: 'Game opened somewhere else',
    detail: 'You are connected to this game in another tab or window. Only one can play at a time.',
  },
  protocol: { title: 'Connection error', detail: 'The server closed the connection. Reload the page to try again.' },
}

function Blocked({ reason, onReconnect }: { reason: FatalReason; onReconnect: () => void }) {
  const { logout } = useAuth()
  const { title, detail } = FATAL_MESSAGES[reason]
  return (
    <div role="alert" className="panel mx-auto mt-10 max-w-md p-8 text-center">
      <h1 className="font-display text-2xl font-semibold">{title}</h1>
      <p className="mt-2 text-ink-300">{detail}</p>
      <div className="mt-6 flex justify-center gap-3">
        {reason === 'replaced' && <Button onClick={onReconnect}>Play here instead</Button>}
        {reason === 'unauthorized' && <Button onClick={logout}>Sign in again</Button>}
        <Link to="/play" className={buttonStyles('secondary')}>
          Back to dashboard
        </Link>
      </div>
    </div>
  )
}

function statusLine(game: GameState, viewer: PlayerColor, opponentConnected: boolean) {
  if (isOver(game)) {
    const verdict = verdictFor(game, viewer)
    return { title: verdict.title, detail: verdict.detail }
  }
  const opponent = game.players[opposite(viewer)].username
  if (game.status === 'waiting') {
    return {
      title: `Waiting for ${opponent}`,
      detail: 'The clocks start when you are both here. The game is cancelled if it has not started within a minute.',
    }
  }
  const check = game.is_check ? ' Check!' : ''
  const away = opponentConnected ? '' : ` ${opponent} is disconnected, and their clock keeps running.`
  return game.turn === viewer
    ? { title: 'Your move', detail: `You are playing ${viewer}.${check}${opponentConnected ? '' : ` ${opponent} is disconnected.`}` }
    : { title: `${opponent}'s turn`, detail: `Waiting for their move.${check}${away}` }
}

function Controls({ session, game, viewer }: { session: GameSession; game: GameState; viewer: PlayerColor }) {
  const [confirming, setConfirming] = useState(false)
  const online = session.connection === 'open'
  const waiting = game.status === 'waiting'
  const offeredByMe = game.draw_offered_by === viewer

  return (
    <>
      <div className="grid grid-cols-2 gap-2 border-t border-line p-3">
        <Button variant="secondary" onClick={session.offerDraw} disabled={!online || waiting || game.draw_offered_by !== null}>
          <Handshake aria-hidden="true" className="size-4" />
          {offeredByMe ? 'Draw offered' : 'Offer draw'}
        </Button>
        <Button variant="secondary" onClick={() => setConfirming(true)} disabled={!online}>
          <Flag aria-hidden="true" className="size-4" />
          {waiting ? 'Cancel game' : 'Resign'}
        </Button>
      </div>
      {confirming && (
        <Modal title={waiting ? 'Cancel this game?' : 'Resign this game?'} onClose={() => setConfirming(false)}>
          <p className="mt-2 text-ink-300">
            {waiting
              ? 'It has not started, so nothing is recorded.'
              : 'It counts as a loss, and your opponent wins immediately.'}
          </p>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Keep playing
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setConfirming(false)
                session.resign()
              }}
            >
              {waiting ? 'Yes, cancel it' : 'Yes, resign'}
            </Button>
          </div>
        </Modal>
      )}
    </>
  )
}

function GameView({ gameId }: { gameId: string }) {
  const session = useGameSession(gameId)
  const navigate = useNavigate()
  const { start } = useMatchmaking()
  const [resultDismissed, setResultDismissed] = useState(false)
  const { game, color: viewer, connection, fatal, pending, opponentConnected, clockReceivedAt } = session
  const opponentName = game && viewer ? game.players[opposite(viewer)].username : null
  const over = isOver(game)
  // Reloaded when the game ends, so the record includes this result.
  const record = useAsync(`record:${opponentName}:${over}`, async (signal) =>
    opponentName ? (await gamesApi.profile(opponentName, signal)).statistics : null,
  )

  if (fatal) return <Blocked reason={fatal} onReconnect={session.reconnect} />

  if (!game || !viewer) {
    return (
      <div role="status" aria-label="Connecting to the game" className="mx-auto max-w-xl space-y-4">
        <p className="flex items-center justify-center gap-3 text-ink-500">
          <Spinner /> {connection === 'reconnecting' ? 'Cannot reach the game. Retrying…' : 'Connecting to the game…'}
        </p>
        <Skeleton className="h-12" />
        <Skeleton className="aspect-square" />
        <Skeleton className="h-12" />
      </div>
    )
  }

  const opponent = opposite(viewer)
  const status = statusLine(game, viewer, opponentConnected)
  const interactive = connection === 'open' && game.status === 'active' && game.turn === viewer && !pending
  const offerForMe = !over && game.draw_offered_by === opponent

  function findNewGame() {
    void start({ time_control_seconds: game!.time_control_seconds, increment_seconds: game!.increment_seconds })
    navigate('/play')
  }

  const bar = (color: PlayerColor) => (
    <PlayerBar
      game={game}
      color={color}
      isViewer={color === viewer}
      online={color === viewer || over ? null : opponentConnected}
      record={color === viewer ? null : record.data}
      clockReceivedAt={clockReceivedAt}
    />
  )

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="grid grid-cols-[minmax(0,1fr)] items-start gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]"
    >
      {/* The board is capped by the viewport height so both clocks stay on screen. */}
      <div className="mx-auto w-full max-w-[min(100%,max(20rem,calc(100dvh-15rem)))] space-y-3">
        {bar(opponent)}
        <Board
          fen={game.fen}
          orientation={viewer}
          playerColor={viewer}
          legalMoves={game.legal_moves}
          lastMove={game.last_move}
          checkedColor={game.is_check ? game.turn : null}
          interactive={interactive}
          pending={pending}
          onMove={session.sendMove}
        />
        {bar(viewer)}
      </div>

      <aside aria-label="Game panel" className="panel overflow-hidden max-lg:order-last">
        <div className="border-b border-line p-4">
          <p className="eyebrow">
            {formatTimeControl(game.time_control_seconds, game.increment_seconds)} game
            {game.result && ` · ${resultScore(game.result)}`}
          </p>
          <div role="status" data-testid="game-status">
            <h1 className="mt-1.5 font-display text-xl font-semibold">{status.title}</h1>
            <p className="mt-1 text-sm text-ink-500">{status.detail}</p>
          </div>
        </div>

        {connection === 'reconnecting' && !over && (
          <div role="alert" className="flex items-start gap-2.5 border-b border-line bg-danger/10 px-4 py-3 text-sm">
            <WifiOff aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-danger" />
            <span>Connection lost. Reconnecting… The game clock keeps running.</span>
          </div>
        )}

        {offerForMe && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            role="group"
            aria-label="Draw offer"
            className="overflow-hidden border-b border-line bg-accent-500/10"
          >
            <div className="px-4 py-3">
              <p className="text-sm font-medium">{game.players[opponent].username} offers a draw</p>
              <div className="mt-2.5 grid grid-cols-2 gap-2">
                <Button onClick={() => session.respondToDraw(true)}>Accept</Button>
                <Button variant="secondary" onClick={() => session.respondToDraw(false)}>
                  Decline
                </Button>
              </div>
            </div>
          </motion.div>
        )}

        <MoveList moves={game.moves} />

        {over ? (
          <div className="grid gap-2 border-t border-line p-3">
            <Button onClick={findNewGame}>Find a new game</Button>
            <Link to="/play" className={buttonStyles('ghost')}>
              Back to dashboard
            </Link>
          </div>
        ) : (
          <Controls session={session} game={game} viewer={viewer} />
        )}
      </aside>

      {session.endedWhileWatching && !resultDismissed && (
        <ResultDialog game={game} viewer={viewer} onClose={() => setResultDismissed(true)} onNewGame={findNewGame} />
      )}
    </motion.div>
  )
}

export function GamePage() {
  const { gameId = '' } = useParams()
  // A different game is a different session: remount so no state carries over.
  return <GameView key={gameId} gameId={gameId} />
}
