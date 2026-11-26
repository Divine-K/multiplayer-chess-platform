import { config } from '../config'
import { tokenStorage } from '../tokenStorage'

/** An error response from the backend, or a network failure (status 0). */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type UnauthorizedListener = () => void
let unauthorizedListener: UnauthorizedListener | null = null

/** Lets the auth layer end the session when the server rejects a stored token. */
export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListener = listener
  return () => {
    if (unauthorizedListener === listener) unauthorizedListener = null
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  /** Set false for public endpoints (login, register, health). Defaults to true. */
  authenticated?: boolean
  signal?: AbortSignal
}

/** FastAPI returns `detail` as a string, or as a list of validation problems for 422 responses. */
function extractErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const { detail } = payload as { detail: unknown }
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown }
      if (typeof first.msg === 'string') return first.msg
    }
  }
  return fallback
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, authenticated = true, signal } = options

  const headers: Record<string, string> = { Accept: 'application/json' }
  let sentToken: string | null = null
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (authenticated) {
    sentToken = tokenStorage.get()
    if (sentToken) headers.Authorization = `Bearer ${sentToken}`
  }

  let response: Response
  try {
    response = await fetch(`${config.apiBaseUrl}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Cannot reach the server. Check your connection and try again.')
  }

  const payload: unknown = response.status === 204 ? null : await response.json().catch(() => null)

  if (!response.ok) {
    // Ignore late 401s for a token that has since been replaced by a new sign-in.
    if (response.status === 401 && sentToken !== null && sentToken === tokenStorage.get()) {
      unauthorizedListener?.()
    }
    throw new ApiError(response.status, extractErrorMessage(payload, `Request failed (${response.status}).`))
  }
  return payload as T
}
