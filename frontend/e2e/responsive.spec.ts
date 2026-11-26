import { expect, test, type Page } from '@playwright/test'
import { newPlayer, square, startGame } from './support.ts'

const VIEWPORTS = [
  { name: 'small phone', width: 320, height: 640 },
  { name: 'phone', width: 375, height: 740 },
  { name: 'tablet', width: 768, height: 1000 },
  { name: 'desktop', width: 1366, height: 850 },
]

async function expectNoSidewaysScroll(page: Page, where: string) {
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), { message: where })
    .toBeLessThanOrEqual(0)
}

test('public pages fit every screen size', async ({ page }) => {
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport)
    for (const path of ['/', '/login', '/register']) {
      await page.goto(path)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await expectNoSidewaysScroll(page, `${path} on a ${viewport.name}`)
    }
  }
})

test('signed-in pages and a live game fit every screen size', async ({ browser }) => {
  // The longest permitted usernames are the hardest to lay out.
  const first = await newPlayer(browser, 'a_very_long_player_name')
  const [white] = await startGame(first, await newPlayer(browser, 'another_very_long_name'))
  const { page } = white
  const gameUrl = page.url()

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport)
    await page.goto(gameUrl)
    await expect(square(page, 'a1')).toBeVisible()
    await expectNoSidewaysScroll(page, `game on a ${viewport.name}`)

    // The board stays square, fully on screen horizontally, and its squares stay tappable.
    const board = await page.getByRole('group', { name: /chessboard/i }).boundingBox()
    expect(board!.x).toBeGreaterThanOrEqual(0)
    expect(board!.x + board!.width).toBeLessThanOrEqual(viewport.width)
    expect(Math.abs(board!.width - board!.height)).toBeLessThanOrEqual(2)
    expect((await square(page, 'e2').boundingBox())!.width).toBeGreaterThanOrEqual(34)
    for (const timer of await page.getByRole('timer').all()) await expect(timer).toBeInViewport()

    for (const path of ['/play', '/history']) {
      await page.goto(path)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await expectNoSidewaysScroll(page, `${path} on a ${viewport.name}`)
    }
  }

  await page.goto(gameUrl)
  await page.getByRole('button', { name: 'Resign' }).click()
  await page.getByRole('button', { name: 'Yes, resign' }).click()
})
