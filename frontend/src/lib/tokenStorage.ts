/**
 * Persists the JWT access token between page loads.
 *
 * Trade-off: localStorage is readable by any script on the page, so an XSS bug could leak the token.
 * Tokens are short-lived (see ACCESS_TOKEN_EXPIRE_MINUTES) and the app renders no untrusted HTML.
 */

export const TOKEN_KEY = 'chess.accessToken'

export const tokenStorage = {
  get(): string | null {
    try {
      return window.localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string): void {
    window.localStorage.setItem(TOKEN_KEY, token)
  },
  clear(): void {
    window.localStorage.removeItem(TOKEN_KEY)
  },
}
