import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('App', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a healthy status when the backend is ready', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, { status: 'ready', database: 'ok' })))
    render(<App />)
    expect(screen.getByRole('heading', { name: /multiplayer chess platform/i })).toBeInTheDocument()
    expect(await screen.findByText(/api and database are healthy/i)).toBeInTheDocument()
  })

  it('shows an error and lets the user retry when the backend is unreachable', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(jsonResponse(200, { status: 'ready', database: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    expect(await screen.findByText(/backend unavailable/i)).toBeInTheDocument()
    expect(screen.getByText(/cannot reach the server/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /check again/i }))
    expect(await screen.findByText(/api and database are healthy/i)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
