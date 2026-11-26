export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'md' | 'lg'

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-accent-500 text-surface-950 hover:bg-accent-400',
  secondary: 'border border-line-strong bg-surface-800 text-ink-100 hover:bg-surface-700',
  ghost: 'text-ink-300 hover:bg-surface-800 hover:text-ink-100',
  danger: 'bg-danger text-surface-950 hover:brightness-110',
}

const SIZES: Record<ButtonSize, string> = {
  md: 'px-4 py-2.5 text-sm',
  lg: 'px-6 py-3.5 text-base',
}

/** Shared by <Button> and by links that should look like buttons. */
export function buttonStyles(variant: ButtonVariant = 'primary', size: ButtonSize = 'md'): string {
  return `inline-flex items-center justify-center gap-2 rounded-lg font-medium transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 disabled:active:scale-100 ${VARIANTS[variant]} ${SIZES[size]}`
}
