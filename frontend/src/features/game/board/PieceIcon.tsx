import type { ReactNode } from 'react'
import type { PieceColor, PieceType } from '../chess'

/** Original flat silhouettes drawn on a 45×45 grid. `detail` strokes use the outline colour. */
const BASE = <path d="M11 39.5v-2.8c0-.9.7-1.7 1.7-1.7h19.6c1 0 1.7.8 1.7 1.7v2.8z" />

const SHAPES: Record<PieceType, ReactNode> = {
  p: (
    <>
      <path d="M13.500 35c.4-5.500 4.800-7.600 6-14h-3.2v-2.800h3c-2-1.200-3.300-3.300-3.300-5.700a6.500 6.500 0 0 1 13 0c0 2.4-1.3 4.5-3.300 5.700h3V21h-3.2c1.200 6.400 5.600 8.500 6 14z" />
      {BASE}
    </>
  ),
  r: (
    <>
      <path d="M13 35l1.500-4h1.800l.9-13.500-3.700-3V7h5v3.500h2.500V7h3v3.5h2.500V7h5v7.500l-3.700 3 .9 13.500h1.800L32 35z" />
      <path data-detail d="M17.2 17.5h10.6M16.4 31h12.200" />
      {BASE}
    </>
  ),
  b: (
    <>
      <path d="M15 35l1.200-4.500c-1.8-1.7-2.700-4-2.7-6.5 0-5.2 4.5-9.7 7.7-12.600a3.200 3.200 0 1 1 2.600 0c3.2 2.900 7.7 7.4 7.7 12.600 0 2.500-.9 4.800-2.700 6.5L30 35z" />
      <path data-detail d="M25.800 16.500l-5.300 6.500M16.4 30.5h12.2" />
      {BASE}
    </>
  ),
  n: (
    <>
      <path d="M15 35c0-6.500 7.5-9 8-15-2 1.8-4.5 2.2-6.500 2.5-2 .3-2.700 3.2-5.200 2.700-2-.5-3-2.700-2-4.7l5.700-8.500V6.500l4.500 3.8c8.5.5 14 7.7 14 16.2 0 3.500-1.2 6-2.200 8.500z" />
      <path data-detail d="M18.2 14.5h.1M12.300 22.3l.9-.8" />
      {BASE}
    </>
  ),
  q: (
    <>
      <path d="M13.500 35l1-5L8.500 14l7.5 8 1.8-11.5L22.500 21l4.700-10.5L29 22l7.5-8-6 16 1 5z" />
      <circle cx="8.500" cy="12" r="2.6" />
      <circle cx="17.500" cy="8.8" r="2.6" />
      <circle cx="27.500" cy="8.8" r="2.6" />
      <circle cx="36.500" cy="12" r="2.6" />
      <path data-detail d="M14.500 30h16" />
      {BASE}
    </>
  ),
  k: (
    <>
      <path d="M21 4.500h3v3h3v3h-3v4.800h-3v-4.8h-3v-3h3z" />
      <path d="M14 35l.8-5c-3.800-3-6.300-5.500-6.300-9.700 0-3.8 3-6.500 6.600-6.5 3.3 0 6 2 7.400 4.700 1.400-2.7 4.100-4.700 7.4-4.7 3.600 0 6.6 2.7 6.6 6.500 0 4.200-2.5 6.700-6.3 9.700l.8 5z" />
      <path data-detail d="M14.8 30h15.4M22.500 18.5V30" />
      {BASE}
    </>
  ),
}

const PALETTE: Record<PieceColor, { fill: string; line: string; detail: string }> = {
  w: { fill: '#f6f1e7', line: '#2b2f38', detail: '#2b2f38' },
  b: { fill: '#262a33', line: '#0d0f13', detail: '#cfd5df' },
}

export function PieceIcon({
  type,
  color,
  className = 'size-full',
}: {
  type: PieceType
  color: PieceColor
  className?: string
}) {
  const { fill, line, detail } = PALETTE[color]
  return (
    <svg
      viewBox="0 0 45 45"
      className={`${className} [&_[data-detail]]:fill-none [&_[data-detail]]:stroke-[var(--piece-detail)]`}
      style={{ '--piece-detail': detail } as React.CSSProperties}
      fill={fill}
      stroke={line}
      strokeWidth={1.4}
      strokeLinejoin="round"
      strokeLinecap="round"
      aria-hidden="true"
    >
      {SHAPES[type]}
    </svg>
  )
}
