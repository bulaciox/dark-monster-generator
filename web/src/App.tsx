import { useState } from 'react'
import { Contribute } from '@/views/Contribute'
import { Data } from '@/views/Data'
import { Gallery } from '@/views/Gallery'
import { Monster } from '@/views/Monster'
import { useMediaQuery } from '@/lib/use-media-query'
import { cn } from '@/lib/utils'

const VIEWS = ['Contribute', 'Monster', 'Gallery', 'Data'] as const
type View = (typeof VIEWS)[number]

export default function App() {
  const [view, setView] = useState<View>('Contribute')
  // Remounts Contribute so a second visitor starts from a blank questionnaire.
  const [runId, setRunId] = useState(0)
  // Visitors answer on their phone, so mobile is the questionnaire and
  // nothing else — the other views are a desktop/curation surface.
  const isDesktop = useMediaQuery('(min-width: 768px)')
  const current: View = isDesktop ? view : 'Contribute'

  return (
    <div className="min-h-dvh">
      {/* Visitors fill the questionnaire on their phone, so on mobile the app
          is the form and nothing else: no navigation, no other views. */}
      <header className="sticky top-0 z-10 hidden border-b border-ink-800 bg-ink-950/85 backdrop-blur md:block">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-6 px-6 py-4">
          <h1 className="font-display text-lg tracking-wide text-ink-50">
            Street Monster
          </h1>
          <nav className="flex gap-1">
            {VIEWS.map((v) => (
              <button
                key={v}
                onClick={() => {
                  if (v === 'Contribute') setRunId((r) => r + 1)
                  setView(v)
                }}
                className={cn(
                  'rounded-sm px-3 py-1.5 text-xs uppercase tracking-[0.15em] transition-colors',
                  current === v
                    ? 'bg-ink-800 text-ink-50'
                    : 'text-ink-500 hover:text-ink-300',
                )}
              >
                {v}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main>
        {current === 'Contribute' && (
          <Contribute
            key={runId}
            // On mobile there is nowhere else to go, so finishing starts a
            // fresh questionnaire for the next visitor.
            onFinished={() =>
              isDesktop ? setView('Monster') : setRunId((r) => r + 1)
            }
          />
        )}
        {current === 'Monster' && <Monster />}
        {current === 'Gallery' && <Gallery />}
        {current === 'Data' && <Data />}
      </main>
    </div>
  )
}
