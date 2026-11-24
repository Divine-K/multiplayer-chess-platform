import { CheckCircle2, RefreshCw, XCircle } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { config } from '../../lib/config'
import { useApiStatus } from './useApiStatus'

export function ApiStatusPanel() {
  const { status, recheck } = useApiStatus()

  return (
    <section
      aria-labelledby="api-status-heading"
      className="w-full max-w-md rounded-xl border border-line bg-surface-900 p-6"
    >
      <h2 id="api-status-heading" className="text-sm font-medium text-ink-300">
        Backend connection
      </h2>

      <div role="status" className="mt-4 flex items-center gap-3">
        {status.state === 'checking' && (
          <>
            <Spinner className="size-5 text-ink-500" />
            <span>Checking API…</span>
          </>
        )}
        {status.state === 'ready' && (
          <>
            <CheckCircle2 aria-hidden="true" className="size-5 text-ok" />
            <span>API and database are healthy</span>
          </>
        )}
        {status.state === 'unavailable' && (
          <>
            <XCircle aria-hidden="true" className="size-5 text-danger" />
            <span>Backend unavailable</span>
          </>
        )}
      </div>

      {status.state === 'unavailable' && <p className="mt-2 text-sm text-ink-500">{status.reason}</p>}

      <p className="mt-4 font-mono text-xs text-ink-500">{config.apiBaseUrl}</p>

      <Button variant="secondary" className="mt-5" onClick={recheck} disabled={status.state === 'checking'}>
        <RefreshCw aria-hidden="true" className="size-4" />
        Check again
      </Button>
    </section>
  )
}
