import { useEffect, useRef, useState } from 'react'
import { api, type Monster } from '@/lib/api'

export type ScreenKind = 'story' | 'monster' | 'organ'

// How often each screen asks the server who is on stage. The stage only
// advances every 60s, so a few seconds of latency is invisible; polling this
// way survives machine suspends and network blips with no long-lived
// connection to drop.
const POLL_MS = 3000
const FADE_MS = 1200

export function Screen({ kind }: { kind: ScreenKind }) {
  const [monster, setMonster] = useState<Monster | null>(null)
  const [visible, setVisible] = useState(true)
  const currentId = useRef<string | null>(null)

  useEffect(() => {
    let stopped = false

    async function tick() {
      try {
        const { monster: next } = await api.stage()
        if (stopped) return
        const nextId = next?.id ?? null
        if (nextId === currentId.current) return

        // Preload the image so the fade never reveals a half-loaded frame.
        const url = next ? imageFor(kind, next) : null
        if (url) await preload(url)
        if (stopped) return

        // Fade out, swap, fade in.
        setVisible(false)
        window.setTimeout(() => {
          if (stopped) return
          currentId.current = nextId
          setMonster(next)
          setVisible(true)
        }, FADE_MS / 2)
      } catch {
        // Keep showing whatever is up; try again on the next tick.
      }
    }

    tick()
    const id = window.setInterval(tick, POLL_MS)
    return () => {
      stopped = true
      window.clearInterval(id)
    }
  }, [kind])

  return (
    <div className="flex h-dvh w-dvw items-center justify-center overflow-hidden bg-black">
      <div
        className="flex h-full w-full items-center justify-center transition-opacity"
        style={{ opacity: visible ? 1 : 0, transitionDuration: `${FADE_MS / 2}ms` }}
      >
        {monster ? (
          <Content kind={kind} monster={monster} />
        ) : (
          <p className="text-sm uppercase tracking-[0.4em] text-ink-700">Waiting</p>
        )}
      </div>
    </div>
  )
}

function Content({ kind, monster }: { kind: ScreenKind; monster: Monster }) {
  if (kind === 'story') {
    return (
      <div className="mx-auto max-w-4xl space-y-10 px-16 text-center">
        <p className="text-sm uppercase tracking-[0.4em] text-ink-600">
          No. {monster.number}
        </p>
        {monster.title && (
          <h1 className="font-display text-5xl leading-tight text-ink-50 lg:text-6xl">
            {monster.title}
          </h1>
        )}
        {monster.story && (
          <p className="text-xl leading-relaxed text-ink-200 lg:text-2xl">
            {monster.story}
          </p>
        )}
      </div>
    )
  }

  const url = imageFor(kind, monster)
  if (!url) {
    return (
      <p className="text-sm uppercase tracking-[0.4em] text-ink-700">
        No {kind} image
      </p>
    )
  }
  return (
    <img
      src={url}
      alt={kind}
      className="max-h-full max-w-full object-contain"
    />
  )
}

function imageFor(kind: ScreenKind, monster: Monster): string | null {
  if (kind === 'monster') return monster.silhouette_image_url
  if (kind === 'organ') return monster.organ_image_url
  return null
}

function preload(url: string): Promise<void> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve()
    img.onerror = () => resolve()
    img.src = url
  })
}
