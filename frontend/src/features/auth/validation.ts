/** Mirrors the backend's rules so mistakes show up early. The server validates again. */

export type FieldErrors<K extends string> = Partial<Record<K, string>>

const USERNAME = /^[A-Za-z0-9_]{3,32}$/
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validateEmail(email: string): string | undefined {
  if (!email) return 'Enter your email address.'
  if (!EMAIL.test(email)) return 'Enter a valid email address.'
}

export function validateLogin(values: { email: string; password: string }) {
  const errors: FieldErrors<'email' | 'password'> = {}
  const email = validateEmail(values.email)
  if (email) errors.email = email
  if (!values.password) errors.password = 'Enter your password.'
  return errors
}

export function validateRegistration(values: {
  username: string
  email: string
  password: string
  confirm: string
}) {
  const errors: FieldErrors<'username' | 'email' | 'password' | 'confirm'> = {}
  if (!USERNAME.test(values.username)) {
    errors.username = 'Use 3–32 letters, numbers or underscores.'
  }
  const email = validateEmail(values.email)
  if (email) errors.email = email
  if (values.password.length < 8) errors.password = 'Use at least 8 characters.'
  else if (values.password.length > 128) errors.password = 'Use at most 128 characters.'
  if (values.confirm !== values.password) errors.confirm = 'The passwords do not match.'
  return errors
}
