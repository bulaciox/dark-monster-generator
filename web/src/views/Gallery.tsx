import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api, type Monster } from '@/lib/api'

export function Gallery() {
  const [items, setItems] = useState<Monster[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.monsters().then(setItems).catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="p-10 text-ink-400">{error}</p>
  if (!items)
    return (
      <div className="flex justify-center p-20">
        <Loader2 className="size-5 animate-spin text-ink-500" />
      </div>
    )
  if (!items.length)
    return <p className="p-20 text-center text-ink-500">No monsters yet.</p>

  return (
    <div className="mx-auto w-full max-w-5xl space-y-20 px-6 py-12">
      {items.map((monster) => (
        <section
          key={monster.id}
          className="grid gap-6 sm:grid-cols-[2fr_1fr] sm:items-start"
        >
          <div className="space-y-4">
            {monster.silhouette_image_url && (
              <div className="overflow-hidden rounded-sm border border-ink-800">
                <img
                  src={monster.silhouette_image_url}
                  alt={monster.title || `Monster ${monster.number}`}
                  className="w-full"
                />
              </div>
            )}
            {monster.story && (
              <p className="text-sm leading-relaxed text-ink-200">
                {monster.story}
              </p>
            )}
          </div>

          <div className="space-y-4">
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-[0.3em] text-ink-500">
                No. {monster.number} · {monster.day}
              </p>
              {monster.title && (
                <h3 className="font-display text-xl text-ink-50">
                  {monster.title}
                </h3>
              )}
            </div>

            {monster.organ_image_url && (
              <figure className="space-y-1.5">
                <div className="overflow-hidden rounded-sm border border-ink-800">
                  <img
                    src={monster.organ_image_url}
                    alt={monster.organs[0]?.part ?? 'Organ'}
                    className="w-full"
                  />
                </div>
                <figcaption className="text-[10px] uppercase tracking-widest text-ink-500">
                  {monster.organs
                    .map((o) => `${o.part} · level ${o.level}`)
                    .join(' / ')}
                </figcaption>
              </figure>
            )}
          </div>
        </section>
      ))}
    </div>
  )
}
