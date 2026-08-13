export type FormOptions = {
  emotion_groups: Record<string, string[]>
  responses: string[]
  relations: string[]
  styles: string[]
  min_words: number
}

export type Submission = {
  encountered: boolean
  emotions: string[]
  monster_who: string
  monster_look: string
  monster_effect: string
  responses: string[]
  relation_today: string
}

export type SubmissionResult = {
  kind: 'initial' | 'edit' | 'reanchor' | 'absorbed'
  image_url: string | null
  previous_image_url: string | null
  version: number | null
  iteration: number | null
}

export type Generation = {
  id: string
  prompt: string
  image_url: string
  day: string
  version: number | null
  kind: string
  iteration: number | null
  created_at: string
}

export type MonsterState =
  | { born: false; day: string; iteration: number }
  | {
      born: true
      day: string
      image_url: string
      version: number
      iteration: number
      edits_since_anchor: number
      submission_count: number
      genome_summary: string
      genome: Record<string, unknown>
      versions: Generation[]
    }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    throw new Error(
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join('; ')
          : `Request failed (${response.status})`,
    )
  }
  return response.json() as Promise<T>
}

export const api = {
  formOptions: () => request<FormOptions>('/api/form'),
  monster: () => request<MonsterState>('/api/monster'),
  generations: () => request<Generation[]>('/api/generations'),
  submissions: () => request<Record<string, unknown>[]>('/api/submissions'),
  submit: (submission: Submission) =>
    request<SubmissionResult>('/api/submissions', {
      method: 'POST',
      body: JSON.stringify(submission),
    }),
  reset: () =>
    request<{ iteration: number }>('/api/reset', { method: 'POST' }),
}
