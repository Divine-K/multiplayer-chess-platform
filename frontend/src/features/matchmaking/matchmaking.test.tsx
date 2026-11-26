import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { FakeSocket } from '../../test/fakeSocket'
import { GAME_ID, gameState, idle } from '../../test/fixtures'
import { renderApp, signedInApi } from '../../test/renderApp'

const where = () => screen.getByTestId('location').textContent
const queued = {
  ...idle,
  status: 'queued' as const,
  time_control_seconds: 300,
  increment_seconds: 0,
  queued_since: new Date().toISOString(),
}
const matched = { ...idle, status: 'matched' as const, game_id: GAME_ID, color: 'white' as const }
// Polling runs every two seconds, so allow for one full interval.
const afterPoll = { timeout: 4000 }

async function dashboard() {
  renderApp('/play', { signedIn: true })
  await screen.findByRole('radio', { name: /5\+0/ })
}

describe('matchmaking', () => {
  it('joins with the chosen time control', async () => {
    const api = signedInApi()
    api.on('POST /api/v1/matchmaking', { body: { ...queued, time_control_seconds: 180 } })
    await dashboard()
    await userEvent.click(screen.getByRole('radio', { name: /3\+0/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Play Chess' }))

    expect(await screen.findByText(/searching for a 3\+0 opponent/i)).toBeInTheDocument()
    expect(api.calls('POST /api/v1/matchmaking')[0].body).toEqual({
      time_control_seconds: 180,
      increment_seconds: 0,
    })
  })

  it('polls while queued and opens the game once matched', async () => {
    FakeSocket.install()
    const api = signedInApi()
    api.on('POST /api/v1/matchmaking', () => {
      api.on('GET /api/v1/matchmaking/status', { body: matched })
      return { body: queued }
    })
    await dashboard()
    await userEvent.click(screen.getByRole('button', { name: 'Play Chess' }))

    await waitFor(() => expect(where()).toBe(`/game/${GAME_ID}`), afterPoll)
    expect(screen.getByText(/opponent found/i)).toBeInTheDocument()
  })

  it('opens the game immediately when an opponent was waiting', async () => {
    FakeSocket.install()
    const api = signedInApi()
    api.on('POST /api/v1/matchmaking', { body: matched })
    await dashboard()
    await userEvent.click(screen.getByRole('button', { name: 'Play Chess' }))
    await waitFor(() => expect(where()).toBe(`/game/${GAME_ID}`))
  })

  it('cancels a search', async () => {
    const api = signedInApi()
    api.on('POST /api/v1/matchmaking', { body: queued })
    api.on('DELETE /api/v1/matchmaking', { body: idle })
    await dashboard()
    await userEvent.click(screen.getByRole('button', { name: 'Play Chess' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel search' }))

    expect(await screen.findByRole('button', { name: 'Play Chess' })).toBeEnabled()
    expect(api.calls('DELETE /api/v1/matchmaking')).toHaveLength(1)
  })

  it('goes to the game if a match beat the cancellation', async () => {
    FakeSocket.install()
    const api = signedInApi()
    api.on('POST /api/v1/matchmaking', { body: queued })
    api.on('DELETE /api/v1/matchmaking', { body: matched })
    await dashboard()
    await userEvent.click(screen.getByRole('button', { name: 'Play Chess' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel search' }))
    await waitFor(() => expect(where()).toBe(`/game/${GAME_ID}`))
  })

  it('resumes a queued search after a reload and notices when it expires', async () => {
    const api = signedInApi()
    let polls = 0
    api.on('GET /api/v1/matchmaking/status', () => ({ body: polls++ === 0 ? queued : idle }))
    renderApp('/play', { signedIn: true })

    expect(await screen.findByText(/searching for a 5\+0 opponent/i)).toBeInTheDocument()
    expect(await screen.findByText(/your search expired/i, {}, afterPoll)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Play Chess' })).toBeInTheDocument()
  })

  it('keeps the search visible on other pages', async () => {
    const api = signedInApi()
    api.on('GET /api/v1/matchmaking/status', { body: queued })
    renderApp('/history', { signedIn: true })
    expect(await screen.findByText(/searching for a 5\+0 game/i)).toBeInTheDocument()
  })

  it('explains why a search could not start', async () => {
    const api = signedInApi()
    api.on('POST /api/v1/matchmaking', {
      status: 409,
      body: { detail: 'Finish your current game before finding a new one.' },
    })
    await dashboard()
    await userEvent.click(screen.getByRole('button', { name: 'Play Chess' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Finish your current game')
    // The dashboard looks for that game again.
    await waitFor(() => expect(api.calls('GET /api/v1/games/active').length).toBeGreaterThan(1))
  })

  it('offers to resume an unfinished game instead of starting another', async () => {
    const api = signedInApi()
    api.on('GET /api/v1/games/active', { body: gameState() })
    await dashboard()

    expect(await screen.findByText('You have a game in progress')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /resume game/i })).toHaveAttribute('href', `/game/${GAME_ID}`)
    expect(screen.getByRole('button', { name: 'Play Chess' })).toBeDisabled()
  })

  it('releases the Play button when the unfinished game ends elsewhere', { timeout: 10_000 }, async () => {
    const api = signedInApi()
    api.on('GET /api/v1/games/active', { body: gameState() })
    await dashboard()
    await screen.findByText('You have a game in progress')
    const statisticsLoads = api.calls('GET /api/v1/users/me/statistics').length

    api.on('GET /api/v1/games/active', { body: null })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Play Chess' })).toBeEnabled(), {
      timeout: 7000,
    })
    expect(screen.queryByText('You have a game in progress')).not.toBeInTheDocument()
    await waitFor(() =>
      expect(api.calls('GET /api/v1/users/me/statistics').length).toBeGreaterThan(statisticsLoads),
    )
  })
})
