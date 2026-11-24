import { apiRequest } from './client'

export interface User {
  id: number
  username: string
  email: string
  created_at: string
}

export interface RegisterInput {
  username: string
  email: string
  password: string
}

export interface LoginInput {
  email: string
  password: string
}

interface TokenResponse {
  access_token: string
  token_type: 'bearer'
}

export const authApi = {
  register: (input: RegisterInput) =>
    apiRequest<User>('/api/v1/auth/register', { method: 'POST', body: input, authenticated: false }),

  login: (input: LoginInput) =>
    apiRequest<TokenResponse>('/api/v1/auth/login', { method: 'POST', body: input, authenticated: false }),

  currentUser: (signal?: AbortSignal) => apiRequest<User>('/api/v1/users/me', { signal }),
}
