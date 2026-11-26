import { useId, useState, type InputHTMLAttributes } from 'react'
import { Eye, EyeOff } from 'lucide-react'

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  hint?: string
}

export function TextField({ label, error, hint, type = 'text', ...rest }: TextFieldProps) {
  const id = useId()
  const [revealed, setRevealed] = useState(false)
  const isPassword = type === 'password'
  const message = error ?? hint

  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink-300">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={isPassword && revealed ? 'text' : type}
          aria-invalid={error ? true : undefined}
          aria-describedby={message ? `${id}-message` : undefined}
          className={`w-full rounded-lg border bg-surface-950 px-3.5 py-2.5 text-ink-100 transition-colors outline-none placeholder:text-ink-500/60 focus:border-accent-400 ${error ? 'border-danger' : 'border-line-strong'} ${isPassword ? 'pr-11' : ''}`}
          {...rest}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setRevealed((value) => !value)}
            aria-label={revealed ? 'Hide password' : 'Show password'}
            aria-pressed={revealed}
            className="absolute inset-y-0 right-0 grid w-11 place-items-center text-ink-500 hover:text-ink-100"
          >
            {revealed ? <EyeOff aria-hidden="true" className="size-4" /> : <Eye aria-hidden="true" className="size-4" />}
          </button>
        )}
      </div>
      {message && (
        <p id={`${id}-message`} className={`mt-1.5 text-sm ${error ? 'text-danger' : 'text-ink-500'}`}>
          {message}
        </p>
      )}
    </div>
  )
}
