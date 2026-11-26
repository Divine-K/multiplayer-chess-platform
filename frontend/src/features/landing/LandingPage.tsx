import { motion } from 'framer-motion'
import { ArrowRight, History, RefreshCw, ShieldCheck, Swords, Timer, Users } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Logo } from '../../components/layout/Logo'
import { buttonStyles } from '../../components/ui/buttonStyles'
import { BRAND } from '../../lib/brand'
import { useAuth } from '../auth/authContext'
import { ShowcaseBoard } from './ShowcaseBoard'

const FEATURES = [
  { icon: ShieldCheck, title: 'The server referees', body: 'Every move is validated on the server before either board changes, including castling, en passant and promotion.' },
  { icon: Timer, title: 'Clocks you can trust', body: '3, 5 and 10 minute games, timed by the server. A flag falls even if both players have closed the tab.' },
  { icon: Users, title: 'One-click matchmaking', body: 'Pick a pace and you are paired with the next player waiting for the same one, with colours drawn at random.' },
  { icon: RefreshCw, title: 'Reconnect and carry on', body: 'Refresh or lose your connection and the game is restored exactly as it stands. Your clock keeps running.' },
  { icon: History, title: 'Your record, kept', body: 'Finished games, results, move lists and your win, loss and draw totals are saved to your account.' },
  { icon: Swords, title: 'Complete game endings', body: 'Checkmate, stalemate, insufficient material, repetition, the fifty-move rule, resignation and agreed draws.' },
]

const STEPS = [
  { title: 'Create an account', body: 'A username, an email and a password. That is all it takes.' },
  { title: 'Choose a pace', body: 'Select a time control and press Play Chess. We find your opponent.' },
  { title: 'Play it out', body: 'Moves appear on both boards in real time. The result goes into your history.' },
]

function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.4, delay }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

export function LandingPage() {
  const { state } = useAuth()
  const signedIn = state.status === 'authenticated'
  const playTarget = signedIn ? '/play' : '/register'

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-line bg-surface-950/90 backdrop-blur">
        <nav aria-label="Main" className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
          <Logo />
          <div className="ml-6 hidden gap-6 text-sm text-ink-300 md:flex">
            <a href="#features" className="hover:text-ink-100">Features</a>
            <a href="#how-it-works" className="hover:text-ink-100">How it works</a>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {!signedIn && (
              <Link to="/login" className={buttonStyles('ghost')}>
                Sign in
              </Link>
            )}
            <Link to={playTarget} className={buttonStyles()}>
              {signedIn ? 'Dashboard' : 'Get started'}
            </Link>
          </div>
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:py-24">
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <p className="eyebrow">Real-time multiplayer chess</p>
            <h1 className="mt-4 font-display text-5xl leading-[1.05] font-semibold tracking-tight sm:text-6xl">
              Your move.
              <br />
              <span className="text-accent-300">In real time.</span>
            </h1>
            <p className="mt-5 max-w-md text-lg text-ink-300">
              {BRAND.name} pairs you with another player for a timed game. The server keeps the board and the clocks, so
              both of you always see the same position.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={playTarget} className={buttonStyles('primary', 'lg')}>
                <Swords aria-hidden="true" className="size-5" />
                Play Chess
              </Link>
              <a href="#how-it-works" className={buttonStyles('secondary', 'lg')}>
                How it works <ArrowRight aria-hidden="true" className="size-4" />
              </a>
            </div>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="mx-auto w-full max-w-md"
          >
            <ShowcaseBoard />
          </motion.div>
        </section>

        <section id="features" aria-labelledby="features-heading" className="scroll-mt-16 border-y border-line bg-surface-900">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <p className="eyebrow">Features</p>
            <h2 id="features-heading" className="mt-3 max-w-xl font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              Built so the game is always fair and always in sync.
            </h2>
            <ul className="mt-12 grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ icon: Icon, title, body }, index) => (
                <li key={title}>
                  <Reveal delay={(index % 3) * 0.06} className="border-t border-line-strong pt-5">
                    <Icon aria-hidden="true" className="size-5 text-accent-400" />
                    <h3 className="mt-3 font-semibold">{title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-ink-500">{body}</p>
                  </Reveal>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="how-it-works" aria-labelledby="how-heading" className="mx-auto max-w-6xl scroll-mt-16 px-4 py-20 sm:px-6">
          <p className="eyebrow">How it works</p>
          <h2 id="how-heading" className="mt-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            Three steps to your first game.
          </h2>
          <ol className="mt-12 grid gap-5 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <li key={step.title}>
                <Reveal delay={index * 0.08} className="panel h-full p-6">
                  <span aria-hidden="true" className="font-display text-4xl text-accent-500">{index + 1}</span>
                  <h3 className="mt-4 font-semibold">{step.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ink-500">{step.body}</p>
                </Reveal>
              </li>
            ))}
          </ol>
          <div className="mt-14 text-center">
            <Link to={playTarget} className={buttonStyles('primary', 'lg')}>
              {signedIn ? 'Go to your dashboard' : 'Create your account'}
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-3 px-4 py-8 text-sm text-ink-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <span>
            <span className="font-display text-base text-ink-100">{BRAND.name}</span> · {BRAND.tagline}
          </span>
          <span>Built with React, TypeScript, FastAPI, WebSockets and PostgreSQL.</span>
        </div>
      </footer>
    </div>
  )
}
