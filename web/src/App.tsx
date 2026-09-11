import { useState } from 'react'
import { Contribute } from '@/views/Contribute'
import { Data } from '@/views/Data'
import { FreeGenerate } from '@/views/FreeGenerate'
import { Gallery } from '@/views/Gallery'
import { Monster } from '@/views/Monster'

// The public questionnaire kiosk has no navigation: visitors only ever see
// Contribute, on any screen size. The curation/admin views still exist --
// they're just not linked from anywhere anymore. Reach them by typing their
// path directly (matching the /screen/{name} pattern used for the exhibition
// screens); api.py serves the SPA for these paths too.
const PATH_VIEWS: Record<string, 'Monster' | 'Gallery' | 'Free Generate' | 'Data'> = {
  '/monster': 'Monster',
  '/gallery': 'Gallery',
  '/free-generate': 'Free Generate',
  '/data': 'Data',
}

export default function App() {
  const [pathView] = useState(() => PATH_VIEWS[window.location.pathname])
  // Remounts Contribute so the next visitor starts from a blank questionnaire.
  const [runId, setRunId] = useState(0)

  if (pathView === 'Monster') return <Monster />
  if (pathView === 'Gallery') return <Gallery />
  if (pathView === 'Free Generate') return <FreeGenerate />
  if (pathView === 'Data') return <Data />

  return (
    <Contribute key={runId} onFinished={() => setRunId((r) => r + 1)} />
  )
}
