import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * A selectable chip used for every choice question in the questionnaire.
 * Works for both single and multi select; the parent owns the state.
 */
export function Option({
  label,
  selected,
  onSelect,
  className,
}: {
  label: string
  selected: boolean
  onSelect: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={selected}
      onClick={onSelect}
      className={cn(
        'group inline-flex items-center gap-2 rounded-sm border px-3.5 py-2 text-left text-sm transition-colors',
        selected
          ? 'border-ink-300 bg-ink-700/25 text-ink-50'
          : 'border-ink-700 text-ink-500 hover:border-ink-600 hover:text-ink-300',
        className,
      )}
    >
      <span
        className={cn(
          'flex size-4 shrink-0 items-center justify-center rounded-[3px] border transition-colors',
          selected ? 'border-ink-300 bg-ink-300' : 'border-ink-600',
        )}
      >
        {selected && <Check className="size-3 text-ink-950" strokeWidth={3} />}
      </span>
      {label}
    </button>
  )
}
