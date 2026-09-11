import { useEffect, useRef, useState } from 'react'
import { api, type Monster } from '@/lib/api'

export type ScreenKind = 'story' | 'monster' | 'organ'

// How often each screen asks the server who is on stage. The stage only
// advances every 60s, so a few seconds of latency is invisible; polling this
// way survives machine suspends and network blips with no long-lived
// connection to drop.
const POLL_MS = 3000
const FADE_MS = 1200

// How often the monster screen's animation triggers, picked randomly within
// this range each cycle so the exhibition doesn't fall into an obvious,
// mechanical rhythm.
const ANIMATION_MIN_DELAY_MS = 20000
const ANIMATION_MAX_DELAY_MS = 45000

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

        if (nextId === currentId.current) {
          // Same monster still on stage -- no fade needed, but pick up data
          // that changed since we last displayed it. In particular, the
          // monster screen's animation (silhouette_video_url) is generated in
          // the background and usually isn't ready the moment the monster
          // first appears; without this, a video that finishes mid-display
          // would never be noticed until this monster's turn ended.
          setMonster((prev) => {
            if (!next || !prev) return next
            if (prev.silhouette_video_url === next.silhouette_video_url) return prev
            return next
          })
          return
        }

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

  if (kind === 'monster') {
    if (!monster.silhouette_image_url) {
      return (
        <p className="text-[clamp(0.75rem,2vw,1.5rem)] uppercase tracking-[0.4em] text-ink-700">
          No monster image
        </p>
      )
    }
    return <MonsterContent monster={monster} />
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

// The monster screen: the still silhouette most of the time, but every so
// often (random interval) it comes alive with a short clip of subtle ambient
// motion, plays forward, then plays back to its own starting frame -- which
// is visually identical to the still image, so the swap back is seamless.
//
// The clip itself is generated once per monster, by the server, entirely in
// the forward direction (see generator.generate_silhouette_video). Everything
// about "reverse" and "when" is decided here, client-side: browsers don't
// support smooth negative playbackRate, so reverse is faked by manually
// stepping currentTime backwards every animation frame -- a standard trick,
// though visibly a little less fluid than the native forward playback.
function MonsterContent({ monster }: { monster: Monster }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [animating, setAnimating] = useState(false)
  const rafRef = useRef<number | null>(null)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    const video = videoRef.current
    setAnimating(false)
    video?.pause()
    if (video) video.currentTime = 0

    function clearPending() {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
      if (timerRef.current != null) window.clearTimeout(timerRef.current)
      rafRef.current = null
      timerRef.current = null
    }

    if (!monster.silhouette_video_url) {
      return clearPending
    }

    function scheduleNext() {
      const delay =
        ANIMATION_MIN_DELAY_MS +
        Math.random() * (ANIMATION_MAX_DELAY_MS - ANIMATION_MIN_DELAY_MS)
      timerRef.current = window.setTimeout(playForward, delay)
    }

    function playForward() {
      const v = videoRef.current
      if (!v) return
      v.currentTime = 0
      setAnimating(true)
      v.play().catch(() => {
        // Autoplay blocked for some reason -- skip this cycle, try again later.
        setAnimating(false)
        scheduleNext()
      })
    }

    function playReverse() {
      const v = videoRef.current
      if (!v) return
      const start = performance.now()
      const startTime = v.currentTime || v.duration || 0
      function step(now: number) {
        const elapsed = (now - start) / 1000
        const t = startTime - elapsed
        if (!videoRef.current) return
        if (t <= 0) {
          videoRef.current.currentTime = 0
          setAnimating(false)
          scheduleNext()
          return
        }
        videoRef.current.currentTime = t
        rafRef.current = requestAnimationFrame(step)
      }
      rafRef.current = requestAnimationFrame(step)
    }

    function onEnded() {
      videoRef.current?.pause()
      playReverse()
    }

    video?.addEventListener('ended', onEnded)
    scheduleNext()

    return () => {
      video?.removeEventListener('ended', onEnded)
      clearPending()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monster.id, monster.silhouette_video_url])

  return (
    <div className="relative h-full w-full">
      <img
        src={monster.silhouette_image_url ?? undefined}
        alt="monster"
        className="absolute inset-0 h-full w-full object-contain transition-opacity"
        style={{ opacity: animating ? 0 : 1, transitionDuration: `${FADE_MS / 4}ms` }}
      />
      {monster.silhouette_video_url && (
        <video
          ref={videoRef}
          src={monster.silhouette_video_url}
          muted
          playsInline
          preload="auto"
          className="absolute inset-0 h-full w-full object-contain transition-opacity"
          style={{ opacity: animating ? 1 : 0, transitionDuration: `${FADE_MS / 4}ms` }}
        />
      )}
    </div>
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
        <p className="whitespace-nowrap text-[0.28em] uppercase tracking-[0.4em] text-white">
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
