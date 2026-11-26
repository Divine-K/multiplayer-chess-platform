import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, Info, XCircle } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { ToastContext, type ShowToast, type ToastTone } from './toastContext'

interface Toast {
  id: number
  message: string
  tone: ToastTone
}

const DURATION_MS = 4500
const ICONS = {
  info: <Info aria-hidden="true" className="size-4 text-accent-400" />,
  success: <CheckCircle2 aria-hidden="true" className="size-4 text-ok" />,
  error: <XCircle aria-hidden="true" className="size-4 text-danger" />,
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>())

  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach(clearTimeout)
  }, [])

  const show = useCallback<ShowToast>((message, tone = 'info') => {
    const id = nextId.current++
    // The newest three are enough; a repeated message replaces its older copy.
    setToasts((list) => [...list.filter((t) => t.message !== message).slice(-2), { id, message, tone }])
    const timer = setTimeout(() => {
      timers.current.delete(timer)
      setToasts((list) => list.filter((t) => t.id !== id))
    }, DURATION_MS)
    timers.current.add(timer)
  }, [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4"
      >
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              layout
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              className="flex max-w-md items-center gap-3 rounded-lg border border-line-strong bg-surface-800 px-4 py-3 text-sm shadow-xl"
            >
              {ICONS[toast.tone]}
              {toast.message}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
