import { useEffect, useState } from 'react'
import { ExternalLink, Loader2 } from 'lucide-react'
import { api, type Monster as MonsterType } from '@/lib/api'

const BASE = 'https://darkgallery-monstergenerator.fly.dev'

const SCREENS = [
  { label: 'Story screen', url: `${BASE}/screen/story` },
  { label: 'Monster screen', url: `${BASE}/screen/monster` },
  { label: 'Organ screen', url: `${BASE}/screen/organ` },
] as const

export function Monster() {
  const [monster, setMonster] = useState<MonsterType | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.monsters()
      .then((list) => setMonster(list[0] ?? null))
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="p-10 text-ink-400">{error}</p>
  if (monster === undefined)
    return (
      <div className="flex justify-center p-20">
        <Loader2 className="size-5 animate-spin text-ink-500" />
      </div>
    )

  if (!monster) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24 text-center">
        <p className="font-display text-2xl text-ink-50">
          No monster yet today
        </p>
        <p className="mt-3 text-sm text-ink-400">
          It takes shape with the first contribution of the day.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-12 px-6 py-12">

      {/* Header */}
      <div className="space-y-1 text-center">
        <p className="text-xs uppercase tracking-[0.3em] text-ink-500">
          No. {monster.number} · {monster.monster_type}
        </p>
        {monster.title && (
          <h2 className="font-display text-4xl text-ink-50">{monster.title}</h2>
        )}
      </div>

      {/* Images */}
      <div className="grid gap-6 sm:grid-cols-2">
        {monster.silhouette_image_url && (
          <div className="overflow-hidden rounded-sm border border-ink-800">
            <img src={monster.silhouette_image_url} alt="Silhouette" className="w-full" />
          </div>
        )}
        {monster.organ_image_url && (
          <figure className="space-y-0">
            <div className="overflow-hidden rounded-sm border border-ink-800">
              <img src={monster.organ_image_url} alt="Organ" className="w-full" />
            </div>
            {monster.organs[0] && (
              <figcaption className="pt-2 text-center text-[11px] uppercase tracking-widest text-ink-500">
                {monster.organs[0].part}
              </figcaption>
            )}
          </figure>
        )}
      </div>

      {/* Story */}
      {monster.story && (
        <p className="mx-auto max-w-2xl text-center text-sm leading-relaxed text-ink-200">
          {monster.story}
        </p>
      )}

      {/* Screen links */}
      <section className="space-y-3">
        <h3 className="text-xs uppercase tracking-[0.25em] text-ink-500">
          Exhibition screens
        </h3>
        <div className="flex flex-wrap gap-3">
          {SCREENS.map(({ label, url }) => (
            <a
              key={url}
              href={url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-sm border border-ink-700 px-4 py-2 text-xs uppercase tracking-[0.15em] text-ink-300 transition-colors hover:border-ink-500 hover:text-ink-50"
            >
              {label}
              <ExternalLink className="size-3" />
            </a>
          ))}
        </div>
      </section>
    </div>
  )
}

