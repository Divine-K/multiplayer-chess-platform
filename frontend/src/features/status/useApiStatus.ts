import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../lib/api/client'
import { healthApi } from '../../lib/api/health'

export type ApiStatus =
  | { state: 'checking' }
  | { state: 'ready' }
  | { state: 'unavailable'; reason: string }

async function fetchStatus(signal?: AbortSignal): Promise<ApiStatus | null> {
  try {
    await healthApi.readiness(signal)
    return { state: 'ready' }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return null
    const reason = error instanceof ApiError ? error.message : 'Unexpected error.'
    return { state: 'unavailable', reason }
  }
}

/** Checks backend readiness (including its database) on mount and on demand. */
export function useApiStatus() {
  const [status, setStatus] = useState<ApiStatus>({ state: 'checking' })

  useEffect(() => {
    const controller = new AbortController()
    void fetchStatus(controller.signal).then((result) => {
      if (result) setStatus(result)
    })
    return () => controller.abort()
  }, [])

  const recheck = useCallback(async () => {
    setStatus({ state: 'checking' })
    const result = await fetchStatus()
    if (result) setStatus(result)
  }, [])

  return { status, recheck }
}
