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

export type Organ = {
  part: string
  group: string
  level: number
  transformation: string
}

export type Monster = {
  id: string
  number: number
  day: string
  monster_type: 'human' | 'environmental'
  organ_image_url: string | null
  silhouette_image_url: string | null
  story: string
  title: string
  organs: Organ[]
  identity: Record<string, unknown>
  submission: Partial<Submission>
}

export type FreeGeneration = {
  id: string
  prompt: string
  image_url: string
  created_at: string
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
  monsters: () => request<Monster[]>('/api/monsters'),
  generations: () => request<Generation[]>('/api/generations'),
  stage: () => request<{ monster: Monster | null }>('/api/stage'),
  freeGenerations: () => request<FreeGeneration[]>('/api/free-generations'),
  freeGenerate: (prompt: string) =>
    request<FreeGeneration>('/api/free-generate', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    }),
  submissions: () => request<Record<string, unknown>[]>('/api/submissions'),
  submit: (submission: Submission) =>
    request<Monster>('/api/submissions', {
      method: 'POST',
      body: JSON.stringify(submission),
    }),
  reset: () =>
    request<{ iteration: number }>('/api/reset', { method: 'POST' }),
}
