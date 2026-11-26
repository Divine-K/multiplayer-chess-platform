import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { tokenStorage } from '../../lib/tokenStorage'
import { fakeApi } from '../../test/fakeApi'
import { alice } from '../../test/fixtures'
import { renderApp, signedInApi } from '../../test/renderApp'

const where = () => screen.getByTestId('location').textContent

async function fillLogin(email = 'alice@example.org', password = 'password123') {
  await userEvent.type(screen.getByLabelText('Email'), email)
  await userEvent.type(screen.getByLabelText('Password'), password)
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
}

async function fillRegistration({ confirm = 'password123' } = {}) {
  await userEvent.type(screen.getByLabelText('Username'), 'alice')
  await userEvent.type(screen.getByLabelText('Email'), 'alice@example.org')
  await userEvent.type(screen.getByLabelText('Password'), 'password123')
  await userEvent.type(screen.getByLabelText('Confirm password'), confirm)
  await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
}

describe('sign in', () => {
  it('validates the form before contacting the server', async () => {
    const api = fakeApi()
    renderApp('/login')
    await userEvent.type(screen.getByLabelText('Email'), 'not-an-email')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
    expect(api.requests).toHaveLength(0)
  })

  it('stores the token and opens the dashboard', async () => {
    const api = signedInApi()
    api.on('POST /api/v1/auth/login', { body: { access_token: 'fresh-token', token_type: 'bearer' } })
    renderApp('/login')
    await fillLogin()

    expect(await screen.findByRole('heading', { name: 'alice' })).toBeInTheDocument()
    expect(where()).toBe('/play')
    expect(tokenStorage.get()).toBe('fresh-token')
    expect(api.calls('GET /api/v1/users/me')[0].token).toBe('fresh-token')
  })

  it("shows the server's error and lets the user try again", async () => {
    fakeApi({ 'POST /api/v1/auth/login': { status: 401, body: { detail: 'Incorrect email or password.' } } })
    renderApp('/login')
    await fillLogin()

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled()
    expect(where()).toBe('/login')
    expect(tokenStorage.get()).toBeNull()
  })

  it('shows a busy button while the request is in flight', async () => {
    fakeApi({ 'POST /api/v1/auth/login': () => new Promise(() => {}) })
    renderApp('/login')
    await fillLogin()
    expect(screen.getByRole('button', { name: 'Sign in' })).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled()
  })
})

describe('registration', () => {
  it('requires matching passwords', async () => {
    const api = fakeApi()
    renderApp('/register')
    await fillRegistration({ confirm: 'different123' })
    expect(screen.getByText('The passwords do not match.')).toBeInTheDocument()
    expect(api.requests).toHaveLength(0)
  })

  it('creates the account, signs in and opens the dashboard', async () => {
    const api = signedInApi()
    api.on('POST /api/v1/auth/register', { status: 201, body: alice })
    api.on('POST /api/v1/auth/login', { body: { access_token: 't', token_type: 'bearer' } })
    renderApp('/register')
    await fillRegistration()

    expect(await screen.findByRole('heading', { name: 'alice' })).toBeInTheDocument()
    expect(api.calls('POST /api/v1/auth/register')[0].body).toEqual({
      username: 'alice',
      email: 'alice@example.org',
      password: 'password123',
    })
  })

  it('reports a duplicate account', async () => {
    fakeApi({ 'POST /api/v1/auth/register': { status: 409, body: { detail: 'That username is taken.' } } })
    renderApp('/register')
    await fillRegistration()
    expect(await screen.findByRole('alert')).toHaveTextContent('That username is taken.')
  })
})

describe('sessions', () => {
  it('sends visitors to sign in, then back to the page they wanted', async () => {
    const api = signedInApi()
    api.on('POST /api/v1/auth/login', { body: { access_token: 't', token_type: 'bearer' } })
    renderApp('/history')
    expect(where()).toBe('/login')
    await fillLogin()
    expect(await screen.findByRole('heading', { name: 'Match history' })).toBeInTheDocument()
    expect(where()).toBe('/history')
  })

  it('discards a token the server rejects', async () => {
    fakeApi({ 'GET /api/v1/users/me': { status: 401, body: { detail: 'Invalid or expired token.' } } })
    renderApp('/play', { signedIn: true })
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    expect(tokenStorage.get()).toBeNull()
  })

  it('ends the session when the token expires mid-use', async () => {
    const api = signedInApi()
    api.on('GET /api/v1/users/me/statistics', { status: 401, body: { detail: 'Expired.' } })
    renderApp('/play', { signedIn: true })
    expect(await screen.findByText(/session has expired/i)).toBeInTheDocument()
    await waitFor(() => expect(where()).toBe('/login'))
    expect(tokenStorage.get()).toBeNull()
  })

  it('keeps the token and offers a retry when the server is unreachable', async () => {
    let online = false
    const api = signedInApi()
    api.on('GET /api/v1/users/me', () => {
      if (!online) throw new TypeError('Failed to fetch')
      return { body: alice }
    })
    renderApp('/play', { signedIn: true })

    expect(await screen.findByText(/cannot reach the server/i)).toBeInTheDocument()
    expect(tokenStorage.get()).toBe('test-token')
    online = true
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'alice' })).toBeInTheDocument()
  })

  it('signs out to the landing page', async () => {
    signedInApi()
    renderApp('/play', { signedIn: true })
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))
    expect(where()).toBe('/')
    expect(tokenStorage.get()).toBeNull()
    expect(screen.getByRole('link', { name: 'Get started' })).toBeInTheDocument()
  })
})

describe('landing page', () => {
  it('offers sign-up to visitors', () => {
    fakeApi()
    renderApp('/')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/your move/i)
    expect(screen.getByRole('link', { name: 'Play Chess' })).toHaveAttribute('href', '/register')
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
  })

  it('sends signed-in players to their dashboard', async () => {
    signedInApi()
    renderApp('/', { signedIn: true })
    expect(await screen.findByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/play')
    expect(screen.getByRole('link', { name: 'Play Chess' })).toHaveAttribute('href', '/play')
  })

  it('has a page for unknown addresses', () => {
    fakeApi()
    renderApp('/nowhere')
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })
})
