import { AnimatePresence, motion } from 'framer-motion'
import { Swords } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../../components/ui/Button'
import { ErrorNotice } from '../../components/ui/ErrorNotice'
import { Skeleton } from '../../components/ui/Skeleton'
import { matchmakingApi } from '../../lib/api/games'
import type { TimeControl } from '../../lib/api/types'
import { formatTimeControl } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useMatchmaking } from '../matchmaking/matchmakingContext'
import { useElapsedSeconds } from '../matchmaking/useElapsedSeconds'

const PREFERENCE_KEY = 'chess.timeControl'
const keyOf = (c: TimeControl) => formatTimeControl(c.time_control_seconds, c.increment_seconds)

function Searching({ since, label, cancelling, onCancel }: { since: number; label: string; cancelling: boolean; onCancel: () => void }) {
  const elapsed = useElapsedSeconds(since)
  return (
    <div className="flex flex-col items-center py-4 text-center">
      <div aria-hidden="true" className="relative grid size-20 place-items-center">
        {[0, 1].map((ring) => (
          <motion.span
            key={ring}
            className="absolute inset-0 rounded-full border border-accent-500"
            initial={{ scale: 0.45, opacity: 0.8 }}
            animate={{ scale: 1.15, opacity: 0 }}
            transition={{ duration: 1.8, repeat: Infinity, delay: ring * 0.9, ease: 'easeOut' }}
          />
        ))}
        <Swords className="size-7 text-accent-400" />
      </div>
      <p role="status" className="mt-4 font-medium">
        Searching for a {label} opponent…
      </p>
      <p className="mt-1 text-sm text-ink-500 tabular-nums">{elapsed}s elapsed</p>
      <Button variant="secondary" className="mt-5" onClick={onCancel} loading={cancelling}>
        Cancel search
      </Button>
    </div>
  )
}

export function PlayPanel({ disabled }: { disabled: boolean }) {
  const { search, error, start, cancel } = useMatchmaking()
  const controls = useAsync('time-controls', (signal) => matchmakingApi.timeControls(signal))
  const [preference, setPreference] = useState(() => window.localStorage.getItem(PREFERENCE_KEY))

  const options = controls.data ?? []
  const selected = options.find((c) => keyOf(c) === preference) ?? options[Math.floor(options.length / 2)]

  function choose(control: TimeControl) {
    setPreference(keyOf(control))
    window.localStorage.setItem(PREFERENCE_KEY, keyOf(control))
  }

  return (
    <section aria-labelledby="play-heading" className="panel p-5 sm:p-6">
      <h2 id="play-heading" className="font-display text-2xl font-semibold">
        Quick match
      </h2>
      <p className="mt-1 text-sm text-ink-500">You will be paired with the next player waiting at the same pace.</p>

      <div className="mt-5">
        <AnimatePresence mode="wait" initial={false}>
          {search.phase === 'queued' ? (
            <motion.div key="searching" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Searching
                since={search.since}
                label={formatTimeControl(search.control.time_control_seconds, search.control.increment_seconds)}
                cancelling={search.cancelling}
                onCancel={cancel}
              />
            </motion.div>
          ) : (
            <motion.div key="choose" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              {controls.error ? (
                <ErrorNotice message={controls.error} onRetry={controls.reload} />
              ) : !controls.data ? (
                <Skeleton className="h-20" />
              ) : (
                <fieldset disabled={disabled} className="grid grid-cols-3 gap-2 disabled:opacity-50">
                  <legend className="sr-only">Time control</legend>
                  {options.map((control) => (
                    <label
                      key={keyOf(control)}
                      className="cursor-pointer rounded-lg border border-line-strong bg-surface-950 px-2 py-3 text-center transition-colors hover:border-ink-500 has-checked:border-accent-400 has-checked:bg-accent-500/10 has-focus-visible:outline-2 has-focus-visible:outline-accent-400"
                    >
                      <input
                        type="radio"
                        name="time-control"
                        className="sr-only"
                        checked={selected === control}
                        onChange={() => choose(control)}
                      />
                      <span className="block font-display text-2xl font-semibold">{keyOf(control)}</span>
                      <span className="block text-xs text-ink-500">{control.label}</span>
                    </label>
                  ))}
                </fieldset>
              )}
              <Button
                size="lg"
                className="mt-4 w-full"
                disabled={disabled || !selected}
                loading={search.phase === 'joining'}
                onClick={() => selected && start(selected)}
              >
                <Swords aria-hidden="true" className="size-5" />
                Play Chess
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      {error && (
        <div className="mt-4">
          <ErrorNotice message={error} />
        </div>
      )}
    </section>
  )
}
