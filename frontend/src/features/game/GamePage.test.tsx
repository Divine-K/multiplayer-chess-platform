import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { GameState } from '../../lib/api/types'
import { FakeSocket } from '../../test/fakeSocket'
import { GAME_ID, afterE4, gameState, noStats } from '../../test/fixtures'
import { renderApp, signedInApi } from '../../test/renderApp'

const sq = (name: string) => document.querySelector<HTMLElement>(`[data-square="${name}"]`)!
const status = () => screen.getByTestId('game-status')

async function openGame(state: GameState = gameState(), opponentConnected = true) {
  const api = signedInApi()
  api.on('GET /api/v1/users/bob', {
    body: { id: 2, username: 'bob', created_at: state.created_at, statistics: { ...noStats, games_played: 3, wins: 2, losses: 1 } },
  })
  renderApp(`/game/${GAME_ID}`, { signedIn: true })
  await waitFor(() => expect(FakeSocket.instances.length).toBeGreaterThan(0))
  const socket = FakeSocket.latest()
  socket.open()
  socket.emit('connected', { color: 'white', opponent_connected: opponentConnected, state })
  return { api, socket }
}

const finished = (overrides: Partial<GameState>) =>
  gameState({
    status: 'finished',
    version: 9,
    legal_moves: [],
    clocks: { white_ms: 200_000, black_ms: 190_000, running: null },
    ...overrides,
  })

describe('game screen', () => {
  beforeEach(() => FakeSocket.install())

  it('connects to this game’s socket and shows both players', async () => {
    const { socket } = await openGame()
    expect(socket.url).toBe(`ws://localhost:8000/ws/games/${GAME_ID}`)
    expect(socket.sent[0]).toEqual({ type: 'auth', payload: { token: 'test-token' } })
    expect(within(screen.getByTestId('player-black')).getByText('bob')).toBeInTheDocument()
    expect(within(screen.getByTestId('player-white')).getByText('(you)')).toBeInTheDocument()
    expect(screen.getByRole('timer', { name: "bob's clock" })).toHaveTextContent('5:00')
    expect(status()).toHaveTextContent('Your move')
    expect(await screen.findByText('· 2W 1L 0D')).toBeInTheDocument()
  })

  it('sends a move and changes the board only when the server accepts it', async () => {
    const { socket } = await openGame()
    await userEvent.click(sq('e2'))
    await userEvent.click(sq('e4'))

    expect(socket.sent.at(-1)).toEqual({ type: 'move', payload: { from: 'e2', to: 'e4' } })
    expect(sq('e2')).toHaveAccessibleName('e2, white pawn')
    expect(sq('e4')).toHaveAttribute('data-pending', 'true')

    socket.emit('move_accepted', { move: { ply: 1, uci: 'e2e4', san: 'e4', color: 'white' }, state: afterE4() })
    expect(sq('e4')).toHaveAccessibleName('e4, white pawn')
    expect(sq('e4')).not.toHaveAttribute('data-pending')
    expect(within(screen.getByRole('region', { name: 'Move history' })).getByText('e4')).toBeInTheDocument()
    expect(status()).toHaveTextContent("bob's turn")
  })

  it('shows a rejection and keeps the server’s position', async () => {
    const { socket } = await openGame()
    await userEvent.click(sq('e2'))
    await userEvent.click(sq('e4'))
    socket.emit('move_rejected', { code: 'illegal_move', message: 'That move is not legal.', state: gameState() })

    expect(screen.getByText('That move is not legal.')).toBeInTheDocument()
    expect(sq('e2')).toHaveAccessibleName('e2, white pawn')
    expect(document.querySelector('[data-pending]')).toBeNull()
  })

  it('shows the opponent’s move as it arrives', async () => {
    const { socket } = await openGame(afterE4())
    expect(status()).toHaveTextContent("bob's turn")
    socket.emit('move_accepted', {
      move: { ply: 2, uci: 'e7e5', san: 'e5', color: 'black' },
      state: gameState({
        version: 3,
        fen: 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2',
        ply: 2,
        last_move: 'e7e5',
        moves: [
          { ply: 1, uci: 'e2e4', san: 'e4' },
          { ply: 2, uci: 'e7e5', san: 'e5' },
        ],
      }),
    })
    expect(sq('e5')).toHaveAccessibleName('e5, black pawn')
    expect(status()).toHaveTextContent('Your move')
  })

  it('waits for the opponent before the game starts', async () => {
    const { socket } = await openGame(
      gameState({ status: 'waiting', version: 0, legal_moves: [], clocks: { white_ms: 300_000, black_ms: 300_000, running: null } }),
      false,
    )
    expect(status()).toHaveTextContent('Waiting for bob')
    expect(screen.getByRole('button', { name: 'Cancel game' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Offer draw' })).toBeDisabled()
    socket.emit('player_connected', { color: 'black' })
    socket.emit('game_started', { state: gameState() })
    expect(status()).toHaveTextContent('Your move')
  })

  it('shows whether the opponent is connected', async () => {
    const { socket } = await openGame()
    expect(screen.getByRole('img', { name: 'Connected' })).toBeInTheDocument()
    socket.emit('player_disconnected', { color: 'black' })
    expect(screen.getByRole('img', { name: 'Disconnected' })).toBeInTheDocument()
    expect(status()).toHaveTextContent('bob is disconnected')
  })

  it('confirms before resigning', async () => {
    const { socket } = await openGame()
    await userEvent.click(screen.getByRole('button', { name: 'Resign' }))
    await userEvent.click(screen.getByRole('button', { name: 'Keep playing' }))
    expect(socket.typesSent()).not.toContain('resign')
    await userEvent.click(screen.getByRole('button', { name: 'Resign' }))
    await userEvent.click(screen.getByRole('button', { name: 'Yes, resign' }))
    expect(socket.typesSent()).toContain('resign')
  })

  it('answers a draw offer', async () => {
    const { socket } = await openGame()
    socket.emit('draw_offered', { by: 'black', state: gameState({ version: 2, draw_offered_by: 'black' }) })
    const offer = screen.getByRole('group', { name: 'Draw offer' })
    expect(offer).toHaveTextContent('bob offers a draw')
    await userEvent.click(within(offer).getByRole('button', { name: 'Decline' }))
    expect(socket.typesSent()).toContain('decline_draw')
  })

  it('tells the player who offered that it was declined', async () => {
    const { socket } = await openGame()
    await userEvent.click(screen.getByRole('button', { name: 'Offer draw' }))
    expect(socket.typesSent()).toContain('offer_draw')
    socket.emit('draw_offered', { by: 'white', state: gameState({ version: 2, draw_offered_by: 'white' }) })
    expect(screen.getByRole('button', { name: 'Draw offered' })).toBeDisabled()
    socket.emit('draw_declined', { state: gameState({ version: 3 }) })
    expect(screen.getByText('Your draw offer was declined.')).toBeInTheDocument()
  })

  it.each([
    ['black_win', 'resignation', 'You lost', 'bob won by resignation.', '0–1'],
    ['white_win', 'timeout', 'You won', 'You won on time.', '1–0'],
    ['draw', 'insufficient_material', 'Draw', 'drawn by insufficient material', '½–½'],
  ] as const)('announces %s by %s', async (result, reason, title, detail, score) => {
    const { socket } = await openGame()
    socket.emit('game_finished', { state: finished({ result, result_reason: reason }) })
    const dialog = screen.getByRole('dialog', { name: title })
    expect(dialog).toHaveTextContent(detail)
    expect(dialog).toHaveTextContent(score)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Review the board' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Resign' })).not.toBeInTheDocument()
  })

  it('starts a new search at the same pace from the result screen', async () => {
    const { api, socket } = await openGame()
    api.on('POST /api/v1/matchmaking', {
      body: { status: 'queued', game_id: null, color: null, time_control_seconds: 300, increment_seconds: 0, queued_since: null },
    })
    socket.emit('game_finished', { state: finished({ result: 'draw', result_reason: 'stalemate' }) })
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Find a new game' }))

    expect(await screen.findByText(/searching for a 5\+0 opponent/i)).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/play')
    expect(api.calls('POST /api/v1/matchmaking')[0].body).toEqual({ time_control_seconds: 300, increment_seconds: 0 })
    expect(socket.closedWith).toBe(1000)
  })

  it('opens a game that already ended without a pop-up', async () => {
    await openGame(finished({ result: 'draw', result_reason: 'stalemate' }), false)
    expect(status()).toHaveTextContent('Draw')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('img', { name: 'Disconnected' })).not.toBeInTheDocument()
  })

  it('reconnects after a dropped connection and restores the game', async () => {
    const { socket } = await openGame()
    socket.drop(1006)
    expect(screen.getByText(/connection lost/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Resign' })).toBeDisabled()
    await userEvent.click(sq('e2'))
    expect(sq('e2')).toHaveAttribute('aria-pressed', 'false')

    await waitFor(() => expect(FakeSocket.latest()).not.toBe(socket), { timeout: 2000 })
    FakeSocket.latest().open()
    FakeSocket.latest().emit('connected', { color: 'white', opponent_connected: true, state: afterE4() })
    expect(screen.queryByText(/connection lost/i)).not.toBeInTheDocument()
    expect(sq('e4')).toHaveAccessibleName('e4, white pawn')
  })

  it('yields to a newer tab and can take the game back', async () => {
    const { socket } = await openGame()
    socket.drop(4409)
    expect(screen.getByRole('heading', { name: 'Game opened somewhere else' })).toBeInTheDocument()
    const before = FakeSocket.instances.length
    await userEvent.click(screen.getByRole('button', { name: 'Play here instead' }))
    expect(FakeSocket.instances).toHaveLength(before + 1)
  })

  it.each([
    [4403, 'This is not your game'],
    [4404, 'Game not found'],
  ])('explains close code %i', async (code, heading) => {
    const { socket } = await openGame()
    socket.drop(code)
    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
  })

  it('counts the running clock down between server updates', async () => {
    let time = 1000
    vi.spyOn(performance, 'now').mockImplementation(() => time)
    await openGame()
    const mine = screen.getByRole('timer', { name: "alice's clock" })
    time += 4000
    await act(() => new Promise((resolve) => setTimeout(resolve, 250)))
    expect(mine).toHaveTextContent('4:56')
    expect(screen.getByRole('timer', { name: "bob's clock" })).toHaveTextContent('5:00')
  })
})
