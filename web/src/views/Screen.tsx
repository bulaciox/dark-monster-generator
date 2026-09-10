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
        <p className="text-[clamp(0.75rem,2vw,1.5rem)] uppercase tracking-[0.4em] text-white">No monster generated today</p>
        )}
      </div>
    </div>
  )
}

function Content({ kind, monster }: { kind: ScreenKind; monster: Monster }) {
  if (kind === 'story') {
    return <StoryContent monster={monster} />
  }

  const url = imageFor(kind, monster)
  if (!url) {
    return (
      <p className="text-[clamp(0.75rem,2vw,1.5rem)] uppercase tracking-[0.4em] text-ink-700">
        No {kind} image
      </p>
    )
  }
  return (
    <img
      src={url}
      alt={kind}
      className="h-full w-full object-contain"
    />
  )
}

// Sizes the story block (number + title + story) as large as possible while
// always fitting the available screen, whatever its size/aspect ratio and
// however long a given story is. All three lines share one `em`-relative
// font-size, which a binary search grows/shrinks until the block's real,
// re-wrapped layout (at the container's actual width) just fits vertically
// and horizontally -- so long screens/short stories get genuinely bigger
// text instead of empty space, and long stories never overflow.
function StoryContent({ monster }: { monster: Monster }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const fontSize = useFitFontSize(containerRef, contentRef, [monster.id])

  return (
    <div ref={containerRef} className="flex h-full w-full items-center justify-center overflow-hidden px-[4vw] py-[4vh]">
      <div
        ref={contentRef}
        className="flex w-full flex-col items-center gap-[0.5em] text-center"
        style={{ fontSize: `${fontSize}px` }}
      >
        <p className="whitespace-nowrap text-[0.28em] uppercase tracking-[0.4em] text-ink-600">
          No. {monster.number}
        </p>
        {monster.title && (
          <h1 className="font-display text-[1em] leading-tight text-ink-50">{monster.title}</h1>
        )}
        {monster.story && (
          <p className="text-[0.42em] leading-relaxed text-ink-200">{monster.story}</p>
        )}
      </div>
    </div>
  )
}

function useFitFontSize(
  containerRef: React.RefObject<HTMLElement | null>,
  contentRef: React.RefObject<HTMLElement | null>,
  deps: unknown[],
): number {
  const [fontSize, setFontSize] = useState(16)

  useEffect(() => {
    const container = containerRef.current
    const content = contentRef.current
    if (!container || !content) return

    function fits(px: number) {
      content!.style.fontSize = `${px}px`
      return (
        content!.scrollHeight <= container!.clientHeight &&
        content!.scrollWidth <= container!.clientWidth
      )
    }

    function recompute() {
      if (!container || !content) return
      let lo = 8
      let hi = 500
      for (let i = 0; i < 20; i++) {
        const mid = (lo + hi) / 2
        if (fits(mid)) lo = mid
        else hi = mid
      }
      content.style.fontSize = ''
      setFontSize(lo)
    }

    recompute()
    const ro = new ResizeObserver(recompute)
    ro.observe(container)
    window.addEventListener('resize', recompute)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', recompute)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return fontSize
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
