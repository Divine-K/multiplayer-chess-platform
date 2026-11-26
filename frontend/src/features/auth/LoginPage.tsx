import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { ErrorNotice } from '../../components/ui/ErrorNotice'
import { TextField } from '../../components/ui/TextField'
import { useToast } from '../../components/ui/toastContext'
import { ApiError } from '../../lib/api/client'
import { AuthLayout } from './AuthLayout'
import { useAuth } from './authContext'
import { validateLogin } from './validation'

export function LoginPage() {
  const { login } = useAuth()
  const toast = useToast()
  const [values, setValues] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState<ReturnType<typeof validateLogin>>({})
  const [failure, setFailure] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const input = { email: values.email.trim(), password: values.password }
    const problems = validateLogin(input)
    setErrors(problems)
    setFailure(null)
    if (Object.keys(problems).length > 0) return
    setSubmitting(true)
    try {
      await login(input)
      // The route guard moves us on once the session is established.
      toast('Signed in. Good to see you.', 'success')
    } catch (error) {
      setFailure(error instanceof ApiError ? error.message : 'Something went wrong. Please try again.')
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to find your next game.">
      <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-5">
        {failure && <ErrorNotice message={failure} />}
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          value={values.email}
          error={errors.email}
          onChange={(e) => setValues({ ...values, email: e.target.value })}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          value={values.password}
          error={errors.password}
          onChange={(e) => setValues({ ...values, password: e.target.value })}
        />
        <Button type="submit" size="lg" className="w-full" loading={submitting}>
          Sign in
        </Button>
      </form>
      <p className="mt-6 text-sm text-ink-500">
        New here?{' '}
        <Link to="/register" className="font-medium text-accent-400 hover:text-accent-300">
          Create an account
        </Link>
      </p>
    </AuthLayout>
  )
}
