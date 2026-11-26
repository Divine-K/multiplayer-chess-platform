/**
 * Presentation-only helpers for drawing a position the server sent.
 *
 * There are deliberately no chess rules here. Which moves are legal comes from the server's
 * `legal_moves` list, and the server re-validates every move it receives.
 */

export type PieceType = 'p' | 'n' | 'b' | 'r' | 'q' | 'k'
export type PieceColor = 'w' | 'b'
export type PlayerColor = 'white' | 'black'
export type PromotionPiece = 'q' | 'r' | 'b' | 'n'

export interface Piece {
  type: PieceType
  color: PieceColor
}

export const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] as const

export const PIECE_NAMES: Record<PieceType, string> = {
  p: 'pawn',
  n: 'knight',
  b: 'bishop',
  r: 'rook',
  q: 'queen',
  k: 'king',
}

export const PIECE_VALUES: Record<PieceType, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 }

export function opposite(color: PlayerColor): PlayerColor {
  return color === 'white' ? 'black' : 'white'
}

export function pieceColor(color: PlayerColor): PieceColor {
  return color === 'white' ? 'w' : 'b'
}

/** Reads the piece placement field of a FEN string into a square → piece map. */
export function parsePlacement(fen: string): Map<string, Piece> {
  const board = new Map<string, Piece>()
  const ranks = fen.split(' ')[0].split('/')
  ranks.forEach((row, rowIndex) => {
    let file = 0
    for (const char of row) {
      if (/\d/.test(char)) {
        file += Number(char)
        continue
      }
      board.set(`${FILES[file]}${8 - rowIndex}`, {
        type: char.toLowerCase() as PieceType,
        color: char === char.toLowerCase() ? 'b' : 'w',
      })
      file += 1
    }
  })
  return board
}

/** Squares in reading order (top-left first) as seen by a player of the given colour. */
export function orientedSquares(orientation: PlayerColor): string[] {
  const squares: string[] = []
  for (let rank = 8; rank >= 1; rank -= 1) {
    for (const file of FILES) squares.push(`${file}${rank}`)
  }
  return orientation === 'white' ? squares : squares.reverse()
}

export function isLightSquare(square: string): boolean {
  return (square.charCodeAt(0) - 97 + Number(square[1])) % 2 === 0
}

/** The server's legal moves that start on `from`, as destination squares. */
export function targetsFrom(legalMoves: string[], from: string): Set<string> {
  return new Set(legalMoves.filter((uci) => uci.startsWith(from)).map((uci) => uci.slice(2, 4)))
}

/** The server marks a promotion by listing the move with a trailing piece letter. */
export function isPromotionMove(legalMoves: string[], from: string, to: string): boolean {
  return legalMoves.some((uci) => uci.length === 5 && uci.startsWith(`${from}${to}`))
}

export function findKing(board: Map<string, Piece>, color: PieceColor): string | null {
  for (const [square, piece] of board) {
    if (piece.type === 'k' && piece.color === color) return square
  }
  return null
}

/** Material difference from the captured lists the server reports. Positive means white is ahead. */
export function materialLead(captured: { white: string[]; black: string[] }): number {
  const total = (pieces: string[]) => pieces.reduce((sum, p) => sum + PIECE_VALUES[p as PieceType], 0)
  return total(captured.white) - total(captured.black)
}
