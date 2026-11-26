import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { ErrorNotice } from '../../components/ui/ErrorNotice'
import { TextField } from '../../components/ui/TextField'
import { useToast } from '../../components/ui/toastContext'
import { ApiError } from '../../lib/api/client'
import { AuthLayout } from './AuthLayout'
import { useAuth } from './authContext'
import { validateRegistration } from './validation'

export function RegisterPage() {
  const { register } = useAuth()
  const toast = useToast()
  const [values, setValues] = useState({ username: '', email: '', password: '', confirm: '' })
  const [errors, setErrors] = useState<ReturnType<typeof validateRegistration>>({})
  const [failure, setFailure] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const field = (name: keyof typeof values) => ({
    value: values[name],
    error: errors[name],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setValues({ ...values, [name]: e.target.value }),
  })

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const input = { ...values, username: values.username.trim(), email: values.email.trim() }
    const problems = validateRegistration(input)
    setErrors(problems)
    setFailure(null)
    if (Object.keys(problems).length > 0) return
    setSubmitting(true)
    try {
      await register({ username: input.username, email: input.email, password: input.password })
      toast('Account created. Welcome!', 'success')
    } catch (error) {
      setFailure(error instanceof ApiError ? error.message : 'Something went wrong. Please try again.')
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout title="Create your account" subtitle="It takes less than a minute.">
      <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-5">
        {failure && <ErrorNotice message={failure} />}
        <TextField label="Username" autoComplete="username" hint="Shown to your opponents." {...field('username')} />
        <TextField label="Email" type="email" autoComplete="email" {...field('email')} />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          hint="At least 8 characters."
          {...field('password')}
        />
        <TextField label="Confirm password" type="password" autoComplete="new-password" {...field('confirm')} />
        <Button type="submit" size="lg" className="w-full" loading={submitting}>
          Create account
        </Button>
      </form>
      <p className="mt-6 text-sm text-ink-500">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-accent-400 hover:text-accent-300">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}
