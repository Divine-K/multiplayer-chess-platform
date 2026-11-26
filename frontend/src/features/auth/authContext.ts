import { createContext, useContext } from 'react'
import type { LoginInput, RegisterInput, User } from '../../lib/api/auth'

export type AuthState =
  | { status: 'loading' }
  /** `signedOut` marks a deliberate sign-out, as opposed to never signing in or an expired session. */
  | { status: 'anonymous'; signedOut?: boolean }
  | { status: 'authenticated'; user: User }
  /** A token exists but the server could not be reached to confirm it. */
  | { status: 'unreachable'; message: string }

export interface AuthContextValue {
  state: AuthState
  login: (input: LoginInput) => Promise<void>
  register: (input: RegisterInput) => Promise<void>
  logout: () => void
  retry: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}

/** For screens behind <RequireAuth>, where a user is guaranteed. */
export function useCurrentUser(): User {
  const { state } = useAuth()
  if (state.status !== 'authenticated') throw new Error('useCurrentUser requires a signed-in user')
  return state.user
}
