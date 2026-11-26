import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AFTER_E4_FEN, OPENING_MOVES, START_FEN } from '../../../test/fixtures'
import { Board } from './Board'

type Props = Parameters<typeof Board>[0]

function setup(overrides: Partial<Props> = {}) {
  const onMove = vi.fn()
  const props: Props = {
    fen: START_FEN,
    orientation: 'white',
    playerColor: 'white',
    legalMoves: OPENING_MOVES,
    lastMove: null,
    checkedColor: null,
    interactive: true,
    pending: null,
    onMove,
    ...overrides,
  }
  const view = render(<Board {...props} />)
  const rerender = (next: Partial<Props>) => view.rerender(<Board {...props} {...next} />)
  return { ...view, onMove, rerender }
}

const sq = (name: string) => document.querySelector<HTMLElement>(`[data-square="${name}"]`)!
const targets = () => [...document.querySelectorAll<HTMLElement>('[data-target]')].map((e) => e.dataset.square).sort()
const order = () => [...document.querySelectorAll<HTMLElement>('[data-square]')].map((e) => e.dataset.square)

describe('Board', () => {
  it('draws the position the server sent on 64 squares', () => {
    setup()
    expect(order()).toHaveLength(64)
    expect(sq('e1')).toHaveAccessibleName('e1, white king')
    expect(sq('d8')).toHaveAccessibleName('d8, black queen')
    expect(sq('e4')).toHaveAccessibleName('e4, empty')
    expect(document.querySelectorAll('[data-square] svg')).toHaveLength(32)
  })

  it('turns the board around for black', () => {
    setup({ orientation: 'black' })
    expect(order()[0]).toBe('h1')
    expect(order()[63]).toBe('a8')
  })

  it('highlights exactly the legal destinations of the selected piece and sends the move', async () => {
    const { onMove } = setup()
    await userEvent.click(sq('g1'))
    expect(sq('g1')).toHaveAttribute('aria-pressed', 'true')
    expect(targets()).toEqual(['f3', 'h3'])
    await userEvent.click(sq('f3'))
    expect(onMove).toHaveBeenCalledExactlyOnceWith({ from: 'g1', to: 'f3' })
    expect(targets()).toEqual([])
  })

  it('never sends a move the server did not list', async () => {
    const { onMove } = setup()
    await userEvent.click(sq('e2'))
    await userEvent.click(sq('e5'))
    expect(onMove).not.toHaveBeenCalled()
    expect(sq('e2')).toHaveAttribute('aria-pressed', 'false')
  })

  it('does not move pieces itself: only a new position does', async () => {
    const { rerender } = setup()
    await userEvent.click(sq('e2'))
    await userEvent.click(sq('e4'))
    expect(sq('e2')).toHaveAccessibleName('e2, white pawn')
    rerender({ fen: AFTER_E4_FEN, lastMove: 'e2e4' })
    expect(sq('e4')).toHaveAccessibleName('e4, white pawn')
    expect(sq('e2')).toHaveAttribute('data-last-move', 'true')
    expect(sq('e4')).toHaveAttribute('data-last-move', 'true')
  })

  it('switches and clears the selection', async () => {
    setup()
    await userEvent.click(sq('e2'))
    await userEvent.click(sq('d2'))
    expect(targets()).toEqual(['d3', 'd4'])
    await userEvent.click(sq('d2'))
    expect(targets()).toEqual([])
  })

  it('ignores the opponent’s pieces', async () => {
    setup()
    await userEvent.click(sq('e7'))
    expect(sq('e7')).toHaveAttribute('aria-pressed', 'false')
  })

  it('cannot be used when it is not your turn', async () => {
    const { onMove } = setup({ interactive: false })
    await userEvent.click(sq('e2'))
    await userEvent.click(sq('e4'))
    expect(targets()).toEqual([])
    expect(onMove).not.toHaveBeenCalled()
  })

  it('drops the selection when the position changes underneath it', async () => {
    const { rerender } = setup()
    await userEvent.click(sq('d2'))
    rerender({ fen: AFTER_E4_FEN })
    expect(targets()).toEqual([])
  })

  it('marks the checked king and a pending move', () => {
    setup({ checkedColor: 'black', pending: { from: 'e2', to: 'e4' } })
    expect(sq('e8')).toHaveAttribute('data-check', 'true')
    expect(sq('e8')).toHaveAccessibleName('e8, black king, in check')
    expect(sq('e2')).toHaveAttribute('data-pending', 'true')
    expect(sq('e4')).toHaveAttribute('data-pending', 'true')
  })

  describe('promotion', () => {
    const fen = '8/4P3/8/8/8/8/k7/4K3 w - - 0 1'
    const legalMoves = ['e7e8q', 'e7e8r', 'e7e8b', 'e7e8n']

    it('asks which piece before sending', async () => {
      const { onMove } = setup({ fen, legalMoves })
      await userEvent.click(sq('e7'))
      await userEvent.click(sq('e8'))
      expect(onMove).not.toHaveBeenCalled()
      expect(screen.getByRole('dialog', { name: 'Promote your pawn' })).toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'rook' }))
      expect(onMove).toHaveBeenCalledExactlyOnceWith({ from: 'e7', to: 'e8', promotion: 'r' })
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('can be cancelled', async () => {
      const { onMove } = setup({ fen, legalMoves })
      await userEvent.click(sq('e7'))
      await userEvent.click(sq('e8'))
      await userEvent.keyboard('{Escape}')
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(onMove).not.toHaveBeenCalled()
    })
  })

  describe('drag and drop', () => {
    function drag(from: string, to: string) {
      // jsdom has no layout, so say which element is under the pointer when it is released.
      document.elementFromPoint = () => sq(to)
      fireEvent.pointerDown(sq(from), { button: 0, clientX: 10, clientY: 10 })
      fireEvent(window, new MouseEvent('pointermove', { clientX: 60, clientY: 60 }))
      fireEvent(window, new MouseEvent('pointerup', { clientX: 60, clientY: 60 }))
    }

    it('sends a legal drop', () => {
      const { onMove } = setup()
      drag('e2', 'e4')
      expect(onMove).toHaveBeenCalledExactlyOnceWith({ from: 'e2', to: 'e4' })
    })

    it('ignores an illegal drop', () => {
      const { onMove } = setup()
      drag('e2', 'e5')
      expect(onMove).not.toHaveBeenCalled()
      expect(targets()).toEqual([])
    })

    it('cannot start on an opponent’s piece', () => {
      const { onMove } = setup()
      drag('e7', 'e5')
      expect(onMove).not.toHaveBeenCalled()
    })
  })

  it('can be played from the keyboard', async () => {
    const { onMove } = setup()
    expect(document.querySelectorAll('[data-square][tabindex="0"]')).toHaveLength(1)
    sq('e2').focus()
    await userEvent.keyboard('{Enter}{ArrowUp}{ArrowUp}')
    expect(sq('e4')).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    expect(onMove).toHaveBeenCalledExactlyOnceWith({ from: 'e2', to: 'e4' })
  })

  it('stops arrow keys at the edge of the board', async () => {
    setup()
    sq('h2').focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(sq('h2')).toHaveFocus()
  })
})
