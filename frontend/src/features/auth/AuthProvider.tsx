import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useToast } from '../../components/ui/toastContext'
import { authApi, type LoginInput, type RegisterInput } from '../../lib/api/auth'
import { ApiError, onUnauthorized } from '../../lib/api/client'
import { TOKEN_KEY, tokenStorage } from '../../lib/tokenStorage'
import { AuthContext, type AuthState } from './authContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const toast = useToast()
  const [state, setState] = useState<AuthState>(() =>
    tokenStorage.get() ? { status: 'loading' } : { status: 'anonymous' },
  )
  // Bumped to re-check the stored token (retry, or another tab signing in or out).
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    if (!tokenStorage.get()) return
    const controller = new AbortController()
    authApi.currentUser(controller.signal).then(
      (user) => setState({ status: 'authenticated', user }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 401) {
          tokenStorage.clear()
          setState({ status: 'anonymous' })
        } else {
          const message = error instanceof ApiError ? error.message : 'Something went wrong.'
          setState({ status: 'unreachable', message })
        }
      },
    )
    return () => controller.abort()
  }, [revision])

  const logout = useCallback(() => {
    tokenStorage.clear()
    setState({ status: 'anonymous', signedOut: true })
  }, [])

  useEffect(
    () =>
      onUnauthorized(() => {
        tokenStorage.clear()
        setState({ status: 'anonymous' })
        toast('Your session has expired. Please sign in again.', 'error')
      }),
    [toast],
  )

  // Tabs share the stored token, so follow sign-ins and sign-outs made elsewhere.
  useEffect(() => {
    function handleStorage(event: StorageEvent) {
      if (event.key !== TOKEN_KEY && event.key !== null) return
      if (!tokenStorage.get()) {
        setState({ status: 'anonymous' })
      } else {
        setState({ status: 'loading' })
        setRevision((n) => n + 1)
      }
    }
    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [])

  const login = useCallback(async (input: LoginInput) => {
    const { access_token } = await authApi.login(input)
    tokenStorage.set(access_token)
    try {
      const user = await authApi.currentUser()
      setState({ status: 'authenticated', user })
    } catch (error) {
      tokenStorage.clear()
      throw error
    }
  }, [])

  const register = useCallback(
    async (input: RegisterInput) => {
      await authApi.register(input)
      await login({ email: input.email, password: input.password })
    },
    [login],
  )

  const retry = useCallback(() => {
    setState({ status: 'loading' })
    setRevision((n) => n + 1)
  }, [])

  const value = useMemo(
    () => ({ state, login, register, logout, retry }),
    [state, login, register, logout, retry],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
