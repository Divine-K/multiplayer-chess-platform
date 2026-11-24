/** Typed access to build-time environment variables. */

const DEFAULT_API_BASE_URL = 'http://localhost:8000'

function trimTrailingSlash(url: string): string {
  return url.replace(/\/+$/, '')
}

export const config = {
  apiBaseUrl: trimTrailingSlash(import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL),
} as const

/** Derives the WebSocket origin (ws:// or wss://) from the HTTP API origin. */
export function toWebSocketUrl(path: string, apiBaseUrl: string = config.apiBaseUrl): string {
  const url = new URL(path, `${apiBaseUrl}/`)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}
