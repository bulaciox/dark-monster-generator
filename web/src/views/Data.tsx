import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type MonsterState } from '@/lib/api'

type Submission = Record<string, unknown> & {
  created_at?: string
  data?: Record<string, unknown>
}

export function Data() {
  const [state, setState] = useState<MonsterState | null>(null)
  const [subs, setSubs] = useState<Submission[] | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    api.monster().then(setState).catch((e) => setError(e.message))
    api.submissions().then(setSubs).catch((e) => setError(e.message))
  }
  useEffect(load, [])

  async function reset() {
    try {
      const { iteration } = await api.reset()
      setNotice(`Done. The next contribution will birth Iteration ${iteration}.`)
      setConfirm(false)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reset failed')
    }
  }

  if (error) return <p className="p-10 text-ink-400">{error}</p>
  if (!state)
    return (
      <div className="flex justify-center p-20">
        <Loader2 className="size-5 animate-spin text-ink-500" />
      </div>
    )

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8 px-6 py-12">
      <p className="text-sm text-ink-500">
        Analysis view: raw visitor inputs and the collective genome.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Iteration" value={state.iteration} />
        <Metric label="Version" value={state.born ? state.version : 0} />
        <Metric label="Submissions" value={state.born ? state.submission_count : 0} />
        <Metric
          label="Edits since anchor"
          value={state.born ? state.edits_since_anchor : 0}
        />
      </div>

      {state.born && state.genome_summary && (
        <Card>
          <CardHeader>
            <CardTitle>Today's genome</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto whitespace-pre-wrap text-xs leading-relaxed text-ink-300">
              {state.genome_summary}
            </pre>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Submissions today ({subs?.length ?? 0})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {!subs?.length && <p className="text-sm text-ink-500">No submissions yet.</p>}
          {subs?.map((s, i) => (
            <details key={i} className="rounded-sm border border-ink-800 p-3">
              <summary className="cursor-pointer text-xs uppercase tracking-widest text-ink-500">
                {String(s.created_at ?? '').slice(11, 19)} ·{' '}
                {(s.data as { encountered?: boolean })?.encountered === false
                  ? 'never met a monster'
                  : 'met a monster'}
              </summary>
              <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-ink-300">
                {JSON.stringify(s.data, null, 2)}
              </pre>
            </details>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Reset day</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-ink-500">
            Archives the current monster as Iteration {state.iteration} and starts a
            fresh one with the next contribution. Past versions stay in the Gallery.
          </p>
          {notice && <p className="text-sm text-ink-300">{notice}</p>}
          <label className="flex items-center gap-2 text-sm text-ink-300">
            <input
              type="checkbox"
              checked={confirm}
              onChange={(e) => setConfirm(e.target.checked)}
              className="accent-ink-300"
            />
            I understand: start a new iteration for today
          </label>
          <Button variant="danger" disabled={!confirm} onClick={reset}>
            Reset today's monster
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-sm border border-ink-800 bg-ink-900/60 p-4">
      <p className="text-[10px] uppercase tracking-[0.2em] text-ink-500">{label}</p>
      <p className="mt-1 font-display text-2xl text-ink-50">{value ?? 0}</p>
    </div>
  )
}
