const SIZES = { sm: 'size-8 text-xs', md: 'size-10 text-sm', lg: 'size-14 text-lg' }

function initials(username: string): string {
  const parts = username.split(/_+/).filter(Boolean)
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : (parts[0] ?? '?').slice(0, 2)
  return letters.toUpperCase()
}

export function Avatar({ username, size = 'md' }: { username: string; size?: keyof typeof SIZES }) {
  return (
    <span
      aria-hidden="true"
      className={`grid shrink-0 place-items-center rounded-full border border-line-strong bg-surface-700 font-semibold text-accent-300 ${SIZES[size]}`}
    >
      {initials(username)}
    </span>
  )
}
