import { defineConfig } from '@playwright/test'

/**
 * Browser tests against the real stack. Start PostgreSQL, the API on :8000 and `npm run dev`
 * first. They use the installed Google Chrome, and each player gets an isolated browser context
 * (separate cookies and storage), exactly like two different people.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  // Matchmaking pairs whoever is waiting, so scenarios must not overlap.
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    channel: 'chrome',
    viewport: { width: 1366, height: 850 },
    trace: 'retain-on-failure',
  },
})
