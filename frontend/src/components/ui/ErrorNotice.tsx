import { AlertTriangle } from 'lucide-react'
import { Button } from './Button'

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm">
      <AlertTriangle aria-hidden="true" className="size-4 shrink-0 text-danger" />
      <span className="flex-1">{message}</span>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}
