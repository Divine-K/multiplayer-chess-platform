import { Link } from 'react-router-dom'
import { Logo } from '../components/layout/Logo'
import { buttonStyles } from '../components/ui/buttonStyles'

export function NotFoundPage() {
  return (
    <main className="grid min-h-screen place-items-center px-6 text-center">
      <div>
        <Logo />
        <h1 className="mt-8 font-display text-4xl font-semibold">Page not found</h1>
        <p className="mt-2 text-ink-500">There is nothing on this square.</p>
        <Link to="/" className={`${buttonStyles()} mt-6`}>
          Back home
        </Link>
      </div>
    </main>
  )
}
