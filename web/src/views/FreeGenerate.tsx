import { useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api, type FreeGeneration } from '@/lib/api'

export function FreeGenerate() {
  const [prompt, setPrompt] = useState('')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [items, setItems] = useState<FreeGeneration[] | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    api.freeGenerations().then(setItems).catch(() => setItems([]))
  }, [])

  async function generate() {
    if (!prompt.trim() || generating) return
    setGenerating(true)
    setError(null)
    try {
      const result = await api.freeGenerate(prompt.trim())
      setItems((prev) => [result, ...(prev ?? [])])
      setPrompt('')
      textareaRef.current?.focus()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generation failed')
    } finally {
      setGenerating(false)
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') generate()
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-10 px-6 py-12">
      {/* Input */}
      <div className="space-y-3">
        <h2 className="font-display text-3xl text-ink-50">Free Generate</h2>
        <p className="text-sm text-ink-400">
          Prompt sent directly to FLUX.2 pro — no system prompt, no style
          wrapping. Press{' '}
          <kbd className="rounded border border-ink-700 px-1 py-0.5 text-[11px] text-ink-400">
            ⌘ Enter
          </kbd>{' '}
          or click Generate.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
          <Textarea
            ref={textareaRef}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Describe what you want to generate…"
            className="min-h-[100px] flex-1"
            disabled={generating}
          />
          <Button
            onClick={generate}
            disabled={!prompt.trim() || generating}
            className="shrink-0"
          >
            {generating ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Generating…
              </>
            ) : (
              'Generate'
            )}
          </Button>
        </div>
        {error && <p className="text-sm text-ink-400">{error}</p>}
      </div>

      {/* Grid */}
      {items === null ? (
        <div className="flex justify-center py-10">
          <Loader2 className="size-5 animate-spin text-ink-500" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-center text-sm text-ink-500">
          No generations yet. Write a prompt above.
        </p>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <figure key={item.id} className="space-y-2">
              <div className="overflow-hidden rounded-sm border border-ink-800">
                <img
                  src={item.image_url}
                  alt={item.prompt}
                  className="w-full"
                />
              </div>
              <figcaption className="text-xs leading-relaxed text-ink-400">
                {item.prompt}
              </figcaption>
            </figure>
          ))}
        </div>
      )}
    </div>
  )
}
