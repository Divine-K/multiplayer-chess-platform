import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { summary } from '../../test/fixtures'
import { renderApp, signedInApi } from '../../test/renderApp'

describe('match history', () => {
  it('describes each game from the player’s side', async () => {
    const api = signedInApi()
    api.on('GET /api/v1/games/history', {
      body: {
        items: [
          summary(1),
          summary(2, { outcome: 'draw', result: 'draw', result_reason: 'stalemate', color: 'black' }),
        ],
        total: 2,
        limit: 10,
        offset: 0,
      },
    })
    renderApp('/history', { signedIn: true })

    const first = await screen.findByRole('link', { name: /vs rival_1/ })
    expect(first).toHaveTextContent('Won')
    expect(first).toHaveTextContent('As white · by checkmate')
    expect(first).toHaveTextContent('5+0 · 4 moves')
    expect(first).toHaveAttribute('href', `/game/${summary(1).game_id}`)
    expect(screen.getByRole('link', { name: /vs rival_2/ })).toHaveTextContent('As black · by stalemate')
    expect(screen.queryByRole('navigation', { name: 'Pagination' })).not.toBeInTheDocument()
  })

  it('pages through older games', async () => {
    const api = signedInApi()
    const page = (offset: number) => ({
      body: { items: [summary(offset + 1)], total: 12, limit: 10, offset },
    })
    api.on('GET /api/v1/games/history?limit=10&offset=0', page(0))
    api.on('GET /api/v1/games/history?limit=10&offset=10', page(10))
    renderApp('/history', { signedIn: true })

    const pagination = await screen.findByRole('navigation', { name: 'Pagination' })
    expect(within(pagination).getByRole('button', { name: 'Newer' })).toBeDisabled()
    await userEvent.click(within(pagination).getByRole('button', { name: 'Older' }))
    expect(await screen.findByRole('link', { name: /vs rival_11/ })).toBeInTheDocument()
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Older' })).toBeDisabled()
  })

  it('has an empty state', async () => {
    signedInApi()
    renderApp('/history', { signedIn: true })
    expect(await screen.findByText('No finished games yet')).toBeInTheDocument()
  })

  it('shows loading, then an error that can be retried', async () => {
    const api = signedInApi()
    api.on('GET /api/v1/games/history', { status: 500, body: {} })
    renderApp('/history', { signedIn: true })

    expect(await screen.findByRole('alert')).toHaveTextContent('Request failed (500).')
    api.on('GET /api/v1/games/history', { body: { items: [summary(3)], total: 1, limit: 10, offset: 0 } })
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('link', { name: /vs rival_3/ })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows the real record and recent games on the dashboard', async () => {
    const api = signedInApi()
    api.on('GET /api/v1/users/me/statistics', { body: { games_played: 8, wins: 6, losses: 1, draws: 1 } })
    api.on('GET /api/v1/games/history', { body: { items: [summary(4)], total: 8, limit: 5, offset: 0 } })
    renderApp('/play', { signedIn: true })

    expect(await screen.findByText('8 games played')).toBeInTheDocument()
    expect(screen.getByText('Win rate 75%')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'View all 8' })).toHaveAttribute('href', '/history')
    expect(screen.getByRole('link', { name: /vs rival_4/ })).toBeInTheDocument()
  })
})
