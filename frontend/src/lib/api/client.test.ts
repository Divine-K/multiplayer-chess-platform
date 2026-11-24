import { beforeEach, describe, expect, it, vi } from 'vitest'
import { tokenStorage } from '../tokenStorage'
import { authApi } from './auth'
import { ApiError, apiRequest } from './client'

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(body === null ? null : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('apiRequest', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns parsed JSON for successful responses', async () => {
    mockFetch(200, { status: 'ready' })
    await expect(apiRequest('/health/ready', { authenticated: false })).resolves.toEqual({ status: 'ready' })
  })

  it('attaches the bearer token when one is stored', async () => {
    tokenStorage.set('abc123')
    const fetchMock = mockFetch(200, {})
    await apiRequest('/api/v1/users/me')
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer abc123')
  })

  it('omits the token for public endpoints', async () => {
    tokenStorage.set('abc123')
    const fetchMock = mockFetch(200, {})
    await apiRequest('/health/ready', { authenticated: false })
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
  })

  it('sends JSON bodies with a content type', async () => {
    const fetchMock = mockFetch(200, {})
    await apiRequest('/x', { method: 'POST', body: { a: 1 } })
    const init = fetchMock.mock.calls[0][1]
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"a":1}')
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')
  })

  it('throws ApiError carrying the backend detail message', async () => {
    mockFetch(409, { detail: 'Username or email is already registered.' })
    await expect(apiRequest('/x')).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      message: 'Username or email is already registered.',
    })
  })

  it('extracts the first message from FastAPI validation errors', async () => {
    mockFetch(422, { detail: [{ msg: 'String should have at least 8 characters' }] })
    await expect(apiRequest('/x')).rejects.toThrow('String should have at least 8 characters')
  })

  it('falls back to a generic message when the error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('boom', { status: 500 })))
    await expect(apiRequest('/x')).rejects.toThrow('Request failed (500).')
  })

  it('reports network failures as ApiError with status 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const error = await apiRequest('/x').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
  })
})

describe('authApi', () => {
  it('posts credentials to the login endpoint without a token', async () => {
    tokenStorage.set('stale')
    const fetchMock = mockFetch(200, { access_token: 't', token_type: 'bearer' })
    const result = await authApi.login({ email: 'a@b.co', password: 'password123' })
    expect(result.access_token).toBe('t')
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/v1\/auth\/login$/)
    expect((fetchMock.mock.calls[0][1].headers as Record<string, string>).Authorization).toBeUndefined()
  })
})
