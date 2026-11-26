import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { tokenStorage } from '../lib/tokenStorage'
import { fakeApi } from './fakeApi'
import { alice, idle, noStats, timeControls } from './fixtures'
import { LocationProbe } from './LocationProbe'

/** The routes a signed-in dashboard needs. Tests override the ones they care about. */
export function signedInApi() {
  return fakeApi({
    'GET /api/v1/users/me': { body: alice },
    'GET /api/v1/users/me/statistics': { body: noStats },
    'GET /api/v1/games/active': { body: null },
    'GET /api/v1/games/history': { body: { items: [], total: 0, limit: 5, offset: 0 } },
    'GET /api/v1/matchmaking/time-controls': { body: timeControls },
    'GET /api/v1/matchmaking/status': { body: idle },
  })
}

export function renderApp(path: string, { signedIn = false } = {}) {
  if (signedIn) tokenStorage.set('test-token')
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <LocationProbe />
    </MemoryRouter>,
  )
}
