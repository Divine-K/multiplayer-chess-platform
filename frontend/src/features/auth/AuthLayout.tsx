import { motion } from 'framer-motion'
import type { ReactNode } from 'react'
import { Logo } from '../../components/layout/Logo'
import { ShowcaseBoard } from '../landing/ShowcaseBoard'

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="hidden flex-col justify-between border-r border-line bg-surface-900 p-10 lg:flex">
        <Logo />
        <div className="mx-auto w-full max-w-sm">
          <ShowcaseBoard />
        </div>
        <p className="max-w-sm text-ink-500">Every move is checked by the server before either board changes.</p>
      </aside>
      <main className="flex flex-col px-6 py-8">
        <div className="lg:hidden">
          <Logo />
        </div>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="m-auto w-full max-w-sm py-10"
        >
          <h1 className="font-display text-4xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-2 text-ink-300">{subtitle}</p>
          {children}
        </motion.div>
      </main>
    </div>
  )
}
