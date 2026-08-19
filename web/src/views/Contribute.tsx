import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Option } from '@/components/ui/option'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import { api, type FormOptions, type Monster, type Submission } from '@/lib/api'
import { cn, wordCount } from '@/lib/utils'

/** Q1 starts unanswered, so neither Yes nor No looks pre-selected. */
type Answers = Omit<Submission, 'encountered'> & { encountered: boolean | null }

const EMPTY: Answers = {
  encountered: null,
  emotions: [],
  monster_who: '',
  monster_look: '',
  monster_effect: '',
  responses: [],
  relation_today: '',
}

const TEXT_STEPS = [
  {
    key: 'monster_who' as const,
    title: 'Who or what was the monster in relation to you?',
    help: 'Describe who or what you experienced as the monster and your relationship to it. It might have been someone close to you, a person in authority, an institution, an event or situation, or something within yourself.',
  },
  {
    key: 'monster_look' as const,
    title: 'What did the monster look like?',
    help: 'Describe its appearance — or, if it had no physical form, describe how you imagine it.',
  },
  {
    key: 'monster_effect' as const,
    title: 'How did the monster affect your life?',
    help: 'Describe the impact the monster had on you.',
  },
]

function toggle(list: string[], value: string) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export function Contribute({ onFinished }: { onFinished: () => void }) {
  const [options, setOptions] = useState<FormOptions | null>(null)
  const [answers, setAnswers] = useState<Answers>(EMPTY)
  const [step, setStep] = useState(0)
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<Monster | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.formOptions().then(setOptions).catch((e) => setError(e.message))
  }, [])

  // The No branch collapses the questionnaire to a single emotions step.
  const steps = useMemo(
    () => (answers.encountered ? ['q1', 'who', 'look', 'effect', 'emotions', 'responses', 'today'] : ['q1', 'emotions-no']),
    [answers.encountered],
  )
  const current = steps[step]

  const minWords = options?.min_words ?? 30
  const canAdvance = (() => {
    switch (current) {
      case 'q1':
        return answers.encountered !== null
      case 'who':
        return wordCount(answers.monster_who) >= minWords
      case 'look':
        return wordCount(answers.monster_look) >= minWords
      case 'effect':
        return wordCount(answers.monster_effect) >= minWords
      case 'emotions':
      case 'emotions-no':
        return answers.emotions.length > 0
      case 'responses':
        return answers.responses.length > 0
      case 'today':
        return answers.relation_today !== ''
      default:
        return false
    }
  })()

  const isLast = step === steps.length - 1

  async function send() {
    setSending(true)
    setError(null)
    try {
      setResult(
        await api.submit({ ...answers, encountered: answers.encountered ?? true }),
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setSending(false)
    }
  }

  if (error && !options) {
    return <Centered><p className="text-ink-400">{error}</p></Centered>
  }
  if (!options) {
    return (
      <Centered>
        <Loader2 className="size-5 animate-spin text-ink-500" />
      </Centered>
    )
  }

  if (sending) {
    return (
      <Centered>
        <div className="max-w-md space-y-6 text-center">
          <Loader2 className="mx-auto size-6 animate-spin text-ink-300" />
          <p className="font-display text-2xl text-ink-50">
            Your monster is taking shape
          </p>
          <p className="text-sm leading-relaxed text-ink-500">
            Your answers are being read and given a body. This takes a moment.
          </p>
        </div>
      </Centered>
    )
  }

  if (result) {
    return <Result result={result} onFinished={onFinished} />
  }

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-3xl flex-col px-6 py-10">
      <Progress value={((step + 1) / steps.length) * 100} className="mb-12" />

      <div className="flex-1">
        {current === 'q1' && (
          <Step
            title="Have you ever encountered a monster in your life?"
            help="A monster can be a person, an experience, a fear, an institution, or anything else that felt monstrous to you."
          >
            <div className="flex gap-3">
              {[
                { label: 'Yes', value: true },
                { label: 'No', value: false },
              ].map((o) => (
                <Option
                  key={o.label}
                  label={o.label}
                  selected={answers.encountered === o.value}
                  onSelect={() => {
                    setAnswers({ ...EMPTY, encountered: o.value })
                    setStep(1)
                  }}
                  className="px-8 py-3 text-base"
                />
              ))}
            </div>
          </Step>
        )}

        {TEXT_STEPS.map(
          (t, i) =>
            current === ['who', 'look', 'effect'][i] && (
              <Step key={t.key} title={t.title} help={t.help}>
                <Textarea
                  autoFocus
                  value={answers[t.key]}
                  onChange={(e) => setAnswers({ ...answers, [t.key]: e.target.value })}
                  placeholder="Your answer…"
                />
                <WordMeter count={wordCount(answers[t.key])} min={minWords} />
              </Step>
            ),
        )}

        {(current === 'emotions' || current === 'emotions-no') && (
          <Step
            title={
              answers.encountered
                ? 'Which emotions did the monster evoke in you?'
                : 'Which emotions do you associate with a monster?'
            }
            help="Select all that apply."
          >
            <div className="space-y-7">
              {Object.entries(options.emotion_groups).map(([group, emotions]) => (
                <div key={group}>
                  <h4 className="mb-3 text-xs uppercase tracking-[0.2em] text-ink-500">
                    {group}
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {emotions.map((emotion) => (
                      <Option
                        key={emotion}
                        label={emotion}
                        selected={answers.emotions.includes(emotion)}
                        onSelect={() =>
                          setAnswers({
                            ...answers,
                            emotions: toggle(answers.emotions, emotion),
                          })
                        }
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Step>
        )}

        {current === 'responses' && (
          <Step title="How did you respond to the monster?" help="Select all that apply.">
            <div className="flex flex-wrap gap-2">
              {options.responses.map((r) => (
                <Option
                  key={r}
                  label={r}
                  selected={answers.responses.includes(r)}
                  onSelect={() =>
                    setAnswers({ ...answers, responses: toggle(answers.responses, r) })
                  }
                />
              ))}
            </div>
          </Step>
        )}

        {current === 'today' && (
          <Step
            title="How do you relate to this experience today?"
            help="Select the answer that best describes your experience."
          >
            <div className="flex flex-col items-start gap-2">
              {options.relations.map((r) => (
                <Option
                  key={r}
                  label={r}
                  selected={answers.relation_today === r}
                  onSelect={() => setAnswers({ ...answers, relation_today: r })}
                />
              ))}
            </div>
          </Step>
        )}
      </div>

      {error && <p className="mt-6 text-sm text-ink-400">{error}</p>}

      <div
        className={cn(
          'mt-10 flex items-center',
          // Nothing to go back to on the first question.
          step === 0 ? 'justify-end' : 'justify-between',
        )}
      >
        {step > 0 && (
          <Button variant="ghost" onClick={() => setStep((s) => s - 1)}>
            <ArrowLeft className="size-4" /> Back
          </Button>
        )}
        <Button
          onClick={() => (isLast ? send() : setStep((s) => s + 1))}
          disabled={!canAdvance}
        >
          {isLast ? 'Feed the monster' : 'Continue'} <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
  )
}

function Step({
  title,
  help,
  children,
}: {
  title: string
  help?: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-6">
      <div className="space-y-3">
        <h2 className="font-display text-3xl leading-tight text-ink-50 sm:text-4xl">
          {title}
        </h2>
        {help && <p className="max-w-2xl text-sm leading-relaxed text-ink-200">{help}</p>}
      </div>
      {children}
    </section>
  )
}

function WordMeter({ count, min }: { count: number; min: number }) {
  const done = count >= min
  return (
    <p className={cn('text-xs', done ? 'text-ink-300' : 'text-ink-500')}>
      {done ? `${count} words` : `${count} / ${min} words minimum`}
    </p>
  )
}

function Result({
  result,
  onFinished,
}: {
  result: Monster
  onFinished: () => void
}) {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-10 px-6 py-12">
      <div className="space-y-2 text-center">
        <p className="text-xs uppercase tracking-[0.3em] text-ink-500">
          No. {result.number}
        </p>
        {result.title && (
          <h2 className="font-display text-3xl text-ink-50 sm:text-4xl">
            {result.title}
          </h2>
        )}
      </div>

      {result.silhouette_image_url && (
        <Frame src={result.silhouette_image_url} />
      )}

      {result.story && (
        <p className="mx-auto max-w-xl text-center text-sm leading-relaxed text-ink-200">
          {result.story}
        </p>
      )}

      {result.organ_image_url && (
        <div className="mx-auto max-w-xs space-y-2">
          <Frame src={result.organ_image_url} />
          {result.organs[0] && (
            <p className="text-center text-[11px] uppercase tracking-[0.2em] text-ink-500">
              {result.organs[0].part}
            </p>
          )}
        </div>
      )}

      <div className="flex justify-center">
        <Button variant="outline" onClick={onFinished}>
          Done
        </Button>
      </div>
    </div>
  )
}

function Frame({ src, caption }: { src: string; caption?: string }) {
  return (
    <figure className="space-y-2">
      <div className="relative overflow-hidden rounded-sm border border-ink-800">
        <img src={src} alt={caption ?? 'The monster'} className="w-full" />
      </div>
      {caption && (
        <figcaption className="text-center text-xs uppercase tracking-[0.2em] text-ink-500">
          {caption}
        </figcaption>
      )}
    </figure>
  )
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-dvh items-center justify-center p-6">{children}</div>
}
