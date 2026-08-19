import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api, type Monster } from '@/lib/api'

// The questions as the visitor answered them, so a generation can be read
// against what produced it. This view is the curation surface, not a visitor
// screen, so the answers appear here in full.
const ANSWERS = [
  ['monster_who', 'Q1 · Who or what'],
  ['monster_look', 'Q2 · Appearance'],
  ['monster_effect', 'Q3 · Effect on life'],
] as const

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
    <div className="mx-auto w-full max-w-6xl space-y-24 px-6 py-12">
      {items.map((monster) => (
        <section
          key={monster.id}
          className="grid gap-8 lg:grid-cols-[1.6fr_1fr_1fr] lg:items-start"
        >
          {/* The monster */}
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

          {/* Title and organ */}
          <div className="space-y-4">
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-[0.3em] text-ink-500">
                No. {monster.number} · {monster.monster_type}
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

          {/* What the visitor actually said */}
          <Answers monster={monster} />
        </section>
      ))}
    </div>
  )
}

function Answers({ monster }: { monster: Monster }) {
  const sub = monster.submission
  const lists: [string, string[] | undefined][] = [
    ['Q4 · Emotions', sub.emotions],
    ['Q5 · Response', sub.responses],
  ]

  return (
    <div className="space-y-4 border-l border-ink-800 pl-5">
      <p className="text-[10px] uppercase tracking-[0.3em] text-ink-500">
        {sub.encountered === false ? 'Never met a monster' : 'Their answers'}
      </p>

      {ANSWERS.map(([key, label]) =>
        sub[key] ? (
          <Field key={key} label={label}>
            {sub[key]}
          </Field>
        ) : null,
      )}

      {lists.map(([label, values]) =>
        values?.length ? (
          <Field key={label} label={label}>
            {values.join(' · ')}
          </Field>
        ) : null,
      )}

      {sub.relation_today && (
        <Field label="Q6 · Today">{sub.relation_today}</Field>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] uppercase tracking-widest text-ink-500">
        {label}
      </p>
      <p className="text-xs leading-relaxed text-ink-300">{children}</p>
    </div>
  )
}

