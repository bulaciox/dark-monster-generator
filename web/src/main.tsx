import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { Screen, type ScreenKind } from './views/Screen.tsx'

// The exhibition screen URLs (/screen/story, /screen/monster, /screen/organ)
// render a bare full-screen display instead of the questionnaire app.
const SCREEN_KINDS = ['story', 'monster', 'organ'] as const
const match = window.location.pathname.match(/^\/screen\/(\w+)/)
const kind = match?.[1] as ScreenKind | undefined
const root = SCREEN_KINDS.includes(kind as ScreenKind) ? (
  <Screen kind={kind as ScreenKind} />
) : (
  <App />
)

createRoot(document.getElementById('root')!).render(
  <StrictMode>{root}</StrictMode>,
)
