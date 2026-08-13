import { useCallback, useEffect } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import type { Generation } from '@/lib/api'

/**
 * Full-screen viewer for a day's versions, with keyboard and on-screen
 * navigation through the images of that same day.
 */
export function Lightbox({
  items,
  index,
  onIndexChange,
  onClose,
}: {
  items: Generation[]
  index: number
  onIndexChange: (index: number) => void
  onClose: () => void
}) {
  const go = useCallback(
    (delta: number) => onIndexChange((index + delta + items.length) % items.length),
    [index, items.length, onIndexChange],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight') go(1)
      if (e.key === 'ArrowLeft') go(-1)
    }
    window.addEventListener('keydown', onKey)
    // Keep the page behind from scrolling while the viewer is open.
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [go, onClose])

  const item = items[index]
  if (!item) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Monster viewer"
      className="fixed inset-0 z-50 flex flex-col bg-ink-950/97 backdrop-blur-sm"
      onClick={onClose}
    >
      <header className="flex items-center justify-between px-5 py-4 text-xs uppercase tracking-[0.2em] text-ink-500">
        <span>
          {item.day} · Iteration {item.iteration ?? 1} · v{item.version} · {item.kind}
        </span>
        <div className="flex items-center gap-4">
          <span>
            {index + 1} / {items.length}
          </span>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-ink-500 transition-colors hover:text-ink-50"
          >
            <X className="size-5" />
          </button>
        </div>
      </header>

      <div
        // min-h-0 lets the image respect max-h-full inside the flex column.
        className="flex min-h-0 flex-1 items-center justify-center gap-3 px-3 pb-6"
        onClick={(e) => e.stopPropagation()}
      >
        <NavButton label="Previous" onClick={() => go(-1)} disabled={items.length < 2}>
          <ChevronLeft className="size-6" />
        </NavButton>

        <img
          src={item.image_url}
          alt={`Version ${item.version}`}
          className="max-h-full max-w-full object-contain"
        />

        <NavButton label="Next" onClick={() => go(1)} disabled={items.length < 2}>
          <ChevronRight className="size-6" />
        </NavButton>
      </div>

      {items.length > 1 && (
        <div
          className="flex justify-center gap-2 overflow-x-auto px-5 pb-5"
          onClick={(e) => e.stopPropagation()}
        >
          {items.map((v, i) => (
            <button
              key={v.id}
              onClick={() => onIndexChange(i)}
              aria-label={`Version ${v.version}`}
              aria-current={i === index}
              className={
                'h-14 w-14 shrink-0 overflow-hidden rounded-sm border transition-opacity ' +
                (i === index
                  ? 'border-ink-300 opacity-100'
                  : 'border-ink-800 opacity-50 hover:opacity-90')
              }
            >
              <img src={v.image_url} alt="" className="size-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function NavButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      disabled={disabled}
      className="shrink-0 rounded-sm p-2 text-ink-500 transition-colors hover:text-ink-50 disabled:invisible"
    >
      {children}
    </button>
  )
}
