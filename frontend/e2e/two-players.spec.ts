import { expect, test, type Page } from '@playwright/test'
import {
  chooseAndPlay,
  clickMove,
  clockSeconds,
  expectSamePosition,
  newPlayer,
  play,
  position,
  square,
  startGame,
  watch,
} from './support.ts'

test('two browser sessions play to checkmate through refresh, disconnect and a second tab', async ({ browser }) => {
  const [white, black] = await startGame(await newPlayer(browser, 'ann'), await newPlayer(browser, 'ben'))

  await test.step('both see the same starting position', async () => {
    await expect(black.page.getByRole('group', { name: 'Chessboard, black at the bottom' })).toBeVisible()
    await expectSamePosition(white.page, black.page)
    expect(await position(white.page)).toHaveLength(32)
  })

  await test.step('the player not on turn cannot pick up a piece', async () => {
    await square(black.page, 'e7').click()
    await expect(square(black.page, 'e7')).toHaveAttribute('aria-pressed', 'false')
    await expect(black.page.locator('[data-target]')).toHaveCount(0)
  })

  await test.step('legal moves are highlighted and reach both boards; turns alternate', async () => {
    await square(white.page, 'f2').click()
    await expect(white.page.locator('[data-target]')).toHaveCount(2)
    await square(white.page, 'f2').click()
    await play(white, black, 'f2', 'f3')
    await expect(black.page.getByTestId('game-status')).toContainText('Your move')
    await expect(white.page.getByTestId('game-status')).toContainText(`${black.username}'s turn`)
    await play(black, white, 'e7', 'e5')
    await expectSamePosition(white.page, black.page)
  })

  await test.step('clocks agree between the two sessions', async () => {
    for (const player of [white, black]) {
      const difference = (await clockSeconds(white.page, player.username)) - (await clockSeconds(black.page, player.username))
      expect(Math.abs(difference)).toBeLessThanOrEqual(1)
    }
  })

  await test.step('a refresh restores the game', async () => {
    const before = await position(black.page)
    await black.page.reload()
    await expect(black.page.getByRole('region', { name: 'Move history' })).toContainText('e5')
    expect(await position(black.page)).toEqual(before)
  })

  await test.step('the opponent sees a disconnect and a return', async () => {
    await black.page.close()
    await expect(white.page.getByRole('img', { name: 'Disconnected' })).toBeVisible()
    black.page = await black.context.newPage()
    watch(black, black.page)
    // The dashboard offers the unfinished game.
    await black.page.goto('/play')
    await black.page.getByRole('link', { name: 'Resume game' }).click()
    await expect(white.page.getByRole('img', { name: 'Connected' })).toBeVisible()
    await expectSamePosition(white.page, black.page)
  })

  await test.step('a second tab takes over, and the first can take it back', async () => {
    const secondTab = await black.context.newPage()
    watch(black, secondTab)
    await secondTab.goto(black.page.url())
    await expect(black.page.getByRole('heading', { name: 'Game opened somewhere else' })).toBeVisible()
    await black.page.getByRole('button', { name: 'Play here instead' }).click()
    await expect(secondTab.getByRole('heading', { name: 'Game opened somewhere else' })).toBeVisible()
    await secondTab.close()
    await expect(black.page.getByTestId('game-status')).toContainText(`${white.username}'s turn`)
  })

  await test.step('a draw offer can be declined', async () => {
    await white.page.getByRole('button', { name: 'Offer draw' }).click()
    await black.page.getByRole('button', { name: 'Decline' }).click()
    await expect(white.page.getByText('Your draw offer was declined.')).toBeVisible()
    await expect(white.page.getByRole('button', { name: 'Offer draw' })).toBeEnabled()
  })

  await test.step('checkmate ends the game on both screens', async () => {
    await play(white, black, 'g2', 'g4')
    await play(black, white, 'd8', 'h4')
    await expect(black.page.getByRole('dialog', { name: 'You won' })).toContainText('by checkmate')
    await expect(white.page.getByRole('dialog', { name: 'You lost' })).toContainText('0–1')
    await expect(square(white.page, 'e1')).toHaveAttribute('data-check', 'true')
    await expectSamePosition(white.page, black.page)
  })

  await test.step('results reach statistics and history', async () => {
    for (const [player, outcome, opponent] of [
      [white, 'Lost', black],
      [black, 'Won', white],
    ] as const) {
      await player.page.getByRole('dialog').getByRole('link', { name: 'Back to dashboard' }).click()
      await expect(player.page.getByText('1 game played')).toBeVisible()
      await player.page.getByRole('link', { name: 'History' }).click()
      const row = player.page.getByRole('link', { name: new RegExp(`vs ${opponent.username}`) })
      await expect(row).toContainText(outcome)
      await expect(row).toContainText('by checkmate')
    }
    await white.page.getByRole('link', { name: new RegExp(`vs ${black.username}`) }).click()
    await expect(white.page.getByTestId('game-status')).toContainText('You lost')
    await expect(white.page.getByRole('dialog')).toHaveCount(0)
  })

  expect(white.errors).toEqual([])
  expect(black.errors).toEqual([])
})

test('the server rejects an illegal move from a tampered client', async ({ browser }) => {
  // Rewrites one outgoing move, as a modified client could. The UI itself never offers this move.
  let tamper = false
  const intercept = (page: Page) =>
    page.routeWebSocket(/\/ws\/games\//, (socket) => {
      const server = socket.connectToServer()
      socket.onMessage((raw) => {
        const message = JSON.parse(String(raw))
        if (tamper && message.type === 'move') {
          tamper = false
          message.payload = { from: 'e2', to: 'e5' }
        }
        server.send(JSON.stringify(message))
      })
    })
  const [white, black] = await startGame(
    await newPlayer(browser, 'cat', intercept),
    await newPlayer(browser, 'dan', intercept),
  )
  const before = await position(black.page)

  tamper = true
  await clickMove(white.page, 'e2', 'e4')

  await expect(white.page.getByText(/not a legal move|illegal/i)).toBeVisible()
  expect(await position(white.page)).toEqual(before)
  expect(await position(black.page)).toEqual(before)
  await expect(white.page.getByTestId('game-status')).toContainText('Your move')
  await play(white, black, 'e2', 'e4')

  await test.step('resignation ends the game for both', async () => {
    await black.page.getByRole('button', { name: 'Resign' }).click()
    await black.page.getByRole('button', { name: 'Yes, resign' }).click()
    await expect(white.page.getByRole('dialog', { name: 'You won' })).toContainText('by resignation')
    await expect(black.page.getByRole('dialog', { name: 'You lost' })).toBeVisible()
  })
})

test('drag and drop, captures, promotion and an agreed draw', async ({ browser }) => {
  const [white, black] = await startGame(await newPlayer(browser, 'eve'), await newPlayer(browser, 'fay'))

  await test.step('a piece can be dragged to a legal square', async () => {
    await square(white.page, 'h2').dragTo(square(white.page, 'h4'))
    await expect(square(black.page, 'h4')).toHaveAttribute('aria-label', 'h4, white pawn')
  })

  await test.step('dropping on an illegal square does nothing', async () => {
    await expect(black.page.getByTestId('game-status')).toContainText('Your move')
    await square(black.page, 'g7').dragTo(square(black.page, 'g4'))
    await expect(square(black.page, 'g7')).toHaveAttribute('aria-label', 'g7, black pawn')
    await expect(black.page.getByTestId('game-status')).toContainText('Your move')
  })

  await play(black, white, 'g7', 'g5')
  await play(white, black, 'h4', 'g5')
  await expect(black.page.getByTestId('player-white').getByRole('img', { name: /captured: pawn/i })).toBeVisible()
  await play(black, white, 'h7', 'h6')
  await play(white, black, 'g5', 'h6')
  await play(black, white, 'f8', 'g7')
  await play(white, black, 'h6', 'g7')
  await play(black, white, 'g8', 'f6')

  await test.step('promotion asks for a piece and both boards show it', async () => {
    await clickMove(white.page, 'g7', 'h8')
    await white.page.getByRole('dialog', { name: 'Promote your pawn' }).getByRole('button', { name: 'knight' }).click()
    await expect(square(black.page, 'h8')).toHaveAttribute('aria-label', 'h8, white knight')
    await expectSamePosition(white.page, black.page)
  })

  await test.step('an accepted draw offer ends the game', async () => {
    await black.page.getByRole('button', { name: 'Offer draw' }).click()
    await white.page.getByRole('button', { name: 'Accept' }).click()
    for (const { page } of [white, black]) {
      await expect(page.getByRole('dialog', { name: 'Draw' })).toContainText('by agreement')
    }
  })

  expect(white.errors).toEqual([])
  expect(black.errors).toEqual([])
})

test('a search can be cancelled, survives navigation and a refresh, and sign-out leaves the queue', async ({ browser }) => {
  const player = await newPlayer(browser, 'gil')
  const { page } = player

  await chooseAndPlay(page, '5+0')
  await page.getByRole('button', { name: 'Cancel search' }).click()
  await expect(page.getByRole('button', { name: 'Play Chess' })).toBeVisible()

  await chooseAndPlay(page, '5+0')
  await page.getByRole('link', { name: 'History' }).click()
  await expect(page.getByText(/searching for a 5\+0 game/i)).toBeVisible()
  await page.reload()
  await expect(page.getByText(/searching for a 5\+0 game/i)).toBeVisible()
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/$/)

  // Having left the queue, the player is not paired with the next arrival.
  const other = await newPlayer(browser, 'hal')
  await chooseAndPlay(other.page, '5+0')
  await expect(other.page.getByText(/searching for a 5\+0 opponent/i)).toBeVisible()
  await other.page.getByRole('button', { name: 'Cancel search' }).click()

  await test.step('signing in again works, and a wrong password is refused', async () => {
    await page.goto('/login')
    await page.getByLabel('Email').fill(player.email)
    await page.getByLabel('Password', { exact: true }).fill(`${player.password}-wrong`)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('alert')).toBeVisible()
    await page.getByLabel('Password', { exact: true }).fill(player.password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/play$/)
  })
})
