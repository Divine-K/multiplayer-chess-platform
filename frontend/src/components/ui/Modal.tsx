import { motion } from 'framer-motion'
import { useEffect, useId, useRef, type ReactNode } from 'react'

interface ModalProps {
  title: string
  children: ReactNode
  /** Called for Escape and backdrop clicks. Omit for dialogs that need an explicit choice. */
  onClose?: () => void
}

const FOCUSABLE = 'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function Modal({ title, children, onClose }: ModalProps) {
  const titleId = useId()
  const dialog = useRef<HTMLDivElement>(null)

  // Move focus into the dialog, keep it there, and give it back on close.
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    dialog.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus()
    return () => previous?.focus()
  }, [])

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === 'Escape') onClose?.()
    if (event.key !== 'Tab' || !dialog.current) return
    const items = [...dialog.current.querySelectorAll<HTMLElement>(FOCUSABLE)]
    if (items.length === 0) return
    const first = items[0]
    const last = items[items.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-40 grid place-items-center bg-black/65 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose?.()
      }}
    >
      <motion.div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={handleKeyDown}
        initial={{ y: 12, scale: 0.97 }}
        animate={{ y: 0, scale: 1 }}
        transition={{ type: 'spring', stiffness: 380, damping: 30 }}
        className="panel w-full max-w-sm p-6 shadow-2xl"
      >
        <h2 id={titleId} className="font-display text-2xl font-semibold">
          {title}
        </h2>
        {children}
      </motion.div>
    </motion.div>
  )
}
