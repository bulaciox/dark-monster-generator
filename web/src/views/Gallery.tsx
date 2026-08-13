import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Lightbox } from '@/components/Lightbox'
import { api, type Generation } from '@/lib/api'

export function Gallery() {
  const [items, setItems] = useState<Generation[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Which day's versions are open in the viewer, and at which image.
  const [viewing, setViewing] = useState<{ key: string; index: number } | null>(null)

  useEffect(() => {
    api.generations().then(setItems).catch((e) => setError(e.message))
  }, [])

  // Newest first from the API; group by day + iteration.
  const groups = useMemo(() => {
    const map = new Map<string, Generation[]>()
    for (const item of items ?? []) {
      const key = `${item.day}__${item.iteration ?? 1}`
      map.set(key, [...(map.get(key) ?? []), item])
    }
    return [...map.entries()]
  }, [items])

  if (error) return <p className="p-10 text-ink-400">{error}</p>
  if (!items)
    return (
      <div className="flex justify-center p-20">
        <Loader2 className="size-5 animate-spin text-ink-500" />
      </div>
    )
  if (!items.length)
    return <p className="p-20 text-center text-ink-500">No monsters yet.</p>

  const open = viewing && groups.find(([key]) => key === viewing.key)

  return (
    <div className="mx-auto w-full max-w-5xl space-y-16 px-6 py-12">
      {groups.map(([key, versions]) => {
        const [day, iteration] = key.split('__')
        return (
          <section key={key} className="space-y-5">
            <h3 className="text-xs uppercase tracking-[0.25em] text-ink-500">
              {day} · Iteration {iteration} · {versions.length} versions
            </h3>

            {/* The day's final form: prominent but not overwhelming, so the
                page stays scannable across many days. */}
            <figure className="space-y-2">
              <button
                onClick={() => setViewing({ key, index: 0 })}
                className="block max-w-md cursor-zoom-in overflow-hidden rounded-sm border border-ink-800 transition-opacity hover:opacity-85"
              >
                <img
                  src={versions[0].image_url}
                  alt={`Final form of ${day}`}
                  className="w-full"
                />
              </button>
              <figcaption className="text-[10px] uppercase tracking-widest text-ink-500">
                Final form — click to enlarge
              </figcaption>
            </figure>

            <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
              {versions.map((v, i) => (
                <figure key={v.id} className="space-y-1">
                  <button
                    onClick={() => setViewing({ key, index: i })}
                    className="block w-full cursor-zoom-in overflow-hidden rounded-sm border border-ink-800 transition-opacity hover:opacity-85"
                  >
                    <img src={v.image_url} alt={`Version ${v.version}`} className="w-full" />
                  </button>
                  <figcaption className="text-[10px] uppercase tracking-widest text-ink-500">
                    v{v.version} · {v.kind}
                  </figcaption>
                </figure>
              ))}
            </div>
          </section>
        )
      })}

      {open && viewing && (
        <Lightbox
          items={open[1]}
          index={viewing.index}
          onIndexChange={(index) => setViewing({ ...viewing, index })}
          onClose={() => setViewing(null)}
        />
      )}
    </div>
  )
}
