import { useEffect, useRef, useState } from 'react'
import ChatCore from './ChatCore.jsx'
import './PageShell.css'
import './PageShellTheme.css'

function PageShell() {
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [history, setHistory] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(220)
  const [isDark, setIsDark] = useState(false)
  const [isResizing, setIsResizing] = useState(false)
  const resizeState = useRef(null)
  const previousUserSelect = useRef('')

  async function refreshSessions() {
    const response = await fetch('/api/sessions')
    if (!response.ok) throw new Error(`Could not load sessions (${response.status})`)
    setSessions(await response.json())
  }

  useEffect(() => {
    refreshSessions().catch(() => setSessions([]))
  }, [])

  async function selectSession(sessionId) {
    const response = await fetch(`/api/sessions/${sessionId}/messages`)
    if (!response.ok) return
    setActiveSessionId(sessionId)
    setHistory(await response.json())
  }

  function startNewChat() {
    setActiveSessionId(null)
    setHistory([])
  }

  async function removeSession(event, sessionId) {
    event.stopPropagation()
    const response = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
    if (!response.ok) return
    setSessions((currentSessions) => currentSessions.filter((session) => session.id !== sessionId))
    if (activeSessionId === sessionId) startNewChat()
  }

  function handleSessionCreated(sessionId) {
    setActiveSessionId(sessionId)
    setHistory(null)
    refreshSessions().catch(() => {})
  }

  function startSidebarResize(event) {
    if (sidebarCollapsed) return
    event.preventDefault()
    resizeState.current = { startX: event.clientX, startWidth: sidebarWidth }
    previousUserSelect.current = document.body.style.userSelect
    document.body.style.userSelect = 'none'
    setIsResizing(true)
  }

  useEffect(() => {
    if (!isResizing) return undefined
    function resizeSidebar(event) {
      const nextWidth = resizeState.current.startWidth + event.clientX - resizeState.current.startX
      setSidebarWidth(Math.min(360, Math.max(180, nextWidth)))
    }
    function stopSidebarResize() {
      document.body.style.userSelect = previousUserSelect.current
      resizeState.current = null
      setIsResizing(false)
    }
    window.addEventListener('pointermove', resizeSidebar)
    window.addEventListener('pointerup', stopSidebarResize)
    window.addEventListener('pointercancel', stopSidebarResize)
    return () => {
      window.removeEventListener('pointermove', resizeSidebar)
      window.removeEventListener('pointerup', stopSidebarResize)
      window.removeEventListener('pointercancel', stopSidebarResize)
    }
  }, [isResizing])

  return <main className={`page-stage page-theme${isResizing ? ' is-resizing' : ''}`} data-theme={isDark ? 'dark' : 'light'} style={{ '--sidebar-width': `${sidebarWidth}px` }}><section className="page-window" aria-label="AI GRID Assistant">
    <aside className={`session-sidebar${sidebarCollapsed ? ' collapsed' : ''}`} aria-label="Chat sessions">
      <div className="sidebar-header">
        <button className="new-chat-button" type="button" onClick={startNewChat}><span aria-hidden="true">+</span> New chat</button>
        <button className="sidebar-toggle" type="button" onClick={() => setSidebarCollapsed(true)} aria-label="Collapse sidebar" title="Collapse sidebar"><span aria-hidden="true">‹</span></button>
      </div>
      <div className="session-list">
        {sessions.map((session) => <div className={`session-row${session.id === activeSessionId ? ' active' : ''}`} key={session.id}>
          <button className="session-select" type="button" onClick={() => selectSession(session.id)} title={session.title}>{session.title}</button>
          <button className="session-delete" type="button" onClick={(event) => removeSession(event, session.id)} aria-label={`Delete ${session.title}`} title="Delete session"><span aria-hidden="true">×</span></button>
        </div>)}
      </div>
      <div className="sidebar-resize-handle" role="separator" aria-label="Resize sidebar" onPointerDown={startSidebarResize} />
    </aside>
    <div className={`chat-panel${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}><ChatCore activeSessionId={activeSessionId} history={history} onSessionCreated={handleSessionCreated} headerActions={<><button className="theme-toggle header-theme-toggle" type="button" onClick={() => setIsDark((current) => !current)} aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'} title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}><span aria-hidden="true">{isDark ? '☀' : '☾'}</span></button>{sidebarCollapsed && <button className="sidebar-expand" type="button" onClick={() => setSidebarCollapsed(false)} aria-label="Expand sidebar" title="Expand sidebar"><span aria-hidden="true">›</span></button>}</>} /></div>
  </section></main>
}

export default PageShell