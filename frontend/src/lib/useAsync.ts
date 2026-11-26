import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './api/client'

export interface AsyncState<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
}

interface Snapshot<T> {
  key: string
  data: T | null
  error: string | null
}

/**
 * Loads server data and exposes loading and error states. `key` identifies the request: when it
 * changes (or `reload` is called) the loader runs again and any in-flight request is aborted.
 */
export function useAsync<T>(key: string, load: (signal: AbortSignal) => Promise<T>): AsyncState<T> {
  const [attempt, setAttempt] = useState(0)
  const requestKey = `${key}#${attempt}`
  const [snapshot, setSnapshot] = useState<Snapshot<T>>({ key: '', data: null, error: null })

  const loader = useRef(load)
  useEffect(() => {
    loader.current = load
  })

  useEffect(() => {
    const controller = new AbortController()
    loader.current(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setSnapshot({ key: requestKey, data, error: null })
      },
      (error: unknown) => {
        if (controller.signal.aborted) return
        const message = error instanceof ApiError ? error.message : 'Something went wrong.'
        setSnapshot((previous) => ({ key: requestKey, data: previous.data, error: message }))
      },
    )
    return () => controller.abort()
  }, [requestKey])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  const current = snapshot.key === requestKey
  return { data: snapshot.data, error: current ? snapshot.error : null, loading: !current, reload }
}
