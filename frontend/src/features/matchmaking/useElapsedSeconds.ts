import { useEffect, useState } from 'react'

export function useElapsedSeconds(since: number): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(timer)
  }, [])
  return Math.max(0, Math.floor((now - since) / 1000))
}
