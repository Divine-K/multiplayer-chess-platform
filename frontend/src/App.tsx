import { ApiStatusPanel } from './features/status/ApiStatusPanel'

/** Foundation shell. Routing, auth screens and the game UI are built on Day 3. */
export default function App() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 px-6">
      <header className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Multiplayer Chess Platform</h1>
        <p className="mt-2 text-ink-300">Real-time chess, authoritative server, two players.</p>
      </header>
      <ApiStatusPanel />
    </main>
  )
}
