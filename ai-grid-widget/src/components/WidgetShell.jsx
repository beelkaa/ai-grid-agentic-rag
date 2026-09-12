import { useState } from 'react'
import ChatCore from './ChatCore.jsx'
import './WidgetShell.css'

function WidgetShell() {
  const [isOpen, setIsOpen] = useState(true)
  const [isFullscreen, setIsFullscreen] = useState(false)
  return <main className="widget-stage">
    {isOpen ? <section className={`assistant-window${isFullscreen ? ' fullscreen' : ''}`} aria-label="AI GRID Assistant"><ChatCore headerActions={<><button type="button" className="control-button" onClick={() => setIsFullscreen((current) => !current)} aria-label={isFullscreen ? 'Exit full view' : 'Open full view'} title={isFullscreen ? 'Exit full view' : 'Full view'}><span className={`fullscreen-glyph${isFullscreen ? ' exit' : ''}`} /></button><button type="button" className="control-button close" onClick={() => setIsOpen(false)} aria-label="Minimize assistant" title="Minimize">−</button></>} /></section> : <button className="launcher" type="button" onClick={() => setIsOpen(true)}><span className="brand-mark small" aria-hidden="true"><i /><i /><i /><i /></span><span>Ask AI GRID Assistant</span><b>↑</b></button>}
  </main>
}

export default WidgetShell