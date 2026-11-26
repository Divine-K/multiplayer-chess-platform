import { randomBytes } from 'node:crypto'
import { expect, type Browser, type BrowserContext, type Page } from '@playwright/test'

export interface Player {
  context: BrowserContext
  page: Page
  username: string
  email: string
  password: string
  /** Uncaught exceptions and console errors, which a clean run must not produce. */
  errors: string[]
}

/** Registers a throwaway account through the real sign-up form, in its own browser context. */
export async function newPlayer(browser: Browser, label: string, prepare?: (page: Page) => Promise<void>): Promise<Player> {
  const context = await browser.newContext()
  const page = await context.newPage()
  const id = `${label}_${randomBytes(4).toString('hex')}`
  const player: Player = {
    context,
    page,
    username: id,
    email: `${id}@e2e-players.dev`,
    password: randomBytes(12).toString('base64url'),
    errors: [],
  }
  watch(player, page)
  await prepare?.(page)
  await page.goto('/register')
  await page.getByLabel('Username').fill(player.username)
  await page.getByLabel('Email').fill(player.email)
  await page.getByLabel('Password', { exact: true }).fill(player.password)
  await page.getByLabel('Confirm password').fill(player.password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL(/\/play$/)
  return player
}

export function watch(player: Player, page: Page): void {
  page.on('pageerror', (error) => player.errors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') player.errors.push(message.text())
  })
}

export const square = (page: Page, name: string) => page.locator(`[data-square="${name}"]`)

export async function chooseAndPlay(page: Page, control = '10+0'): Promise<void> {
  await page.getByRole('group', { name: 'Time control' }).getByText(control, { exact: true }).click()
  await page.getByRole('button', { name: 'Play Chess' }).click()
}

/** Queues both players and returns them as [white, black] once both boards are live. */
export async function startGame(first: Player, second: Player): Promise<[Player, Player]> {
  await chooseAndPlay(first.page)
  await expect(first.page.getByText(/searching for a 10\+0 opponent/i)).toBeVisible()
  await chooseAndPlay(second.page)
  for (const { page } of [first, second]) {
    await expect(page).toHaveURL(/\/game\/[0-9a-f-]{36}$/)
    await expect(page.getByTestId('game-status')).toContainText(/your move|'s turn/i)
  }
  expect(first.page.url()).toBe(second.page.url())
  const firstIsWhite = await first.page.getByRole('group', { name: 'Chessboard, white at the bottom' }).isVisible()
  return firstIsWhite ? [first, second] : [second, first]
}

export async function clickMove(page: Page, from: string, to: string): Promise<void> {
  await square(page, from).click()
  await square(page, to).click()
}

/** The position as a sorted list such as "e4 white pawn", independent of board orientation. */
export async function position(page: Page): Promise<string[]> {
  const labels = await page.locator('[data-square]').evaluateAll((nodes) =>
    nodes.map((node) => (node.getAttribute('aria-label') ?? '').split(', ').slice(0, 2).join(' ')),
  )
  return labels.filter((label) => !label.endsWith('empty')).sort()
}

export async function expectSamePosition(a: Page, b: Page): Promise<void> {
  await expect.poll(async () => JSON.stringify(await position(a)) === JSON.stringify(await position(b))).toBe(true)
}

/** Plays a move and waits until both boards show the piece on its destination. */
export async function play(mover: Player, other: Player, from: string, to: string): Promise<void> {
  await expect(mover.page.getByTestId('game-status')).toContainText('Your move')
  await clickMove(mover.page, from, to)
  for (const { page } of [mover, other]) {
    await expect(square(page, from)).toHaveAttribute('aria-label', new RegExp(`^${from}, empty`))
    await expect(square(page, to)).toHaveAttribute('data-last-move', 'true')
  }
}

export async function clockSeconds(page: Page, username: string): Promise<number> {
  const text = await page.getByRole('timer', { name: `${username}'s clock` }).innerText()
  const [minutes, seconds] = text.split(':').map(Number)
  return minutes * 60 + seconds
}
