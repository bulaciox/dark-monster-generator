import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api, type MonsterState } from '@/lib/api'

export function Monster() {
  const [state, setState] = useState<MonsterState | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.monster().then(setState).catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="p-10 text-ink-400">{error}</p>
  if (!state)
    return (
      <div className="flex justify-center p-20">
        <Loader2 className="size-5 animate-spin text-ink-500" />
      </div>
    )

  if (!state.born) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24 text-center">
        <p className="font-display text-2xl text-ink-50">
          Today's monster has not been born yet
        </p>
        <p className="mt-3 text-sm text-ink-500">
          It takes shape with the first contribution of the day.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-10 px-6 py-12">
      <div className="relative overflow-hidden rounded-sm border border-ink-800">
        <img src={state.image_url} alt="Today's monster" className="w-full" />
      </div>

      <p className="text-center text-xs uppercase tracking-[0.25em] text-ink-500">
        Iteration {state.iteration} · Version {state.version} ·{' '}
        {state.submission_count} contributions
      </p>

      {state.versions.length > 1 && (
        <section className="space-y-4">
          <h3 className="font-display text-xl text-ink-50">Evolution</h3>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {state.versions.map((v) => (
              <figure key={v.id} className="space-y-1.5">
                <div className="relative overflow-hidden rounded-sm border border-ink-800">
                  <img src={v.image_url} alt={`Version ${v.version}`} className="w-full" />
                </div>
                <figcaption className="text-[11px] uppercase tracking-widest text-ink-500">
                  v{v.version} · {v.kind}
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
