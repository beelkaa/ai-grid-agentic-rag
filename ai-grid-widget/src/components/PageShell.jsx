import { useEffect, useRef, useState } from 'react'
import ChatCore from './ChatCore.jsx'
import './PageShell.css'
import './PageShellTheme.css'
import './PageShellFix.css'

const suggestedQuestions = [
  { icon: 'robot', title: 'Build an agent', description: 'Chat, tools, agent loops', question: 'How do I build a chat assistant or agent with AI Grid?' },
  { icon: 'list-details', title: 'Browse models', description: 'Current model catalog', question: 'What models are available on AI Grid?' },
  { icon: 'file-text', title: 'OCR and documents', description: 'Scans and PDFs', question: 'How does AI Grid handle OCR for scanned documents?' },
  { icon: 'arrows-diff', title: 'Compare models', description: 'Reasoning and pricing', question: 'Compare two models for a coding agent' },
]

function SidebarIcon({ open }) {
  return <svg className="sidebar-icon" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round"><rect x="2.5" y="3" width="11" height="10" rx="1.5" /><path d="M6 3v10" />{open ? <path d="m4.2 8 1.3-1.3M4.2 8l1.3 1.3" /> : <path d="m11.8 8-1.3-1.3M11.8 8l1.3 1.3" />}</svg>
}

function ControlIcon({ name }) {
  const paths = {
    trash: <path d="M3 5.5h10M6 5.5V4h4v1.5m-6 0 .5 8h7l.5-8M7 7.5v4m2-4v4" />,
    sun: <><circle cx="8" cy="8" r="2.5" /><path d="M8 2v1.2M8 12.8V14M2 8h1.2M12.8 8H14M3.8 3.8l.8.8M11.4 11.4l.8.8M12.2 3.8l-.8.8M4.6 11.4l-.8.8" /></>,
    moon: <path d="M11.8 10.8A4.8 4.8 0 0 1 5.2 4.2 4.8 4.8 0 1 0 11.8 10.8z" />,
  }
  return <svg className="control-icon" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function BrandButton({ collapsed, onClick }) {
  return <button className="sidebar-brand-button" type="button" onClick={onClick} aria-label={collapsed ? 'Expand sidebar' : 'AI GRID Assistant'} title={collapsed ? 'Expand sidebar' : undefined}><span className="brand-mark small" aria-hidden="true"><i /><i /><i /><i /></span><span className="sidebar-brand-copy"><strong>AI GRID</strong><small>Assistant workspace</small></span></button>
}

function PageShell() {
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [history, setHistory] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.innerWidth <= 720)
  const [sidebarWidth, setSidebarWidth] = useState(248)
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

  async function deleteAllChats() {
    if (!sessions.length || !window.confirm('Delete all chats?')) return
    const responses = await Promise.all(sessions.map((session) => fetch(`/api/sessions/${session.id}`, { method: 'DELETE' })))
    if (responses.some((response) => !response.ok)) return
    setSessions([])
    startNewChat()
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
      <div className="sidebar-brand"><BrandButton collapsed={sidebarCollapsed} onClick={() => sidebarCollapsed && setSidebarCollapsed(false)} /><button className="sidebar-toggle" type="button" onClick={() => setSidebarCollapsed(true)} aria-label="Collapse sidebar" title="Collapse sidebar"><SidebarIcon open /></button></div>
      <div className="sidebar-header">
        <button className="new-chat-button" type="button" onClick={startNewChat}><span className="new-chat-icon" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M8 3v10M3 8h10" /></svg></span><span className="new-chat-label">New chat</span></button>
      </div>
      <div className="session-heading">Recent</div><div className="session-list">
        {sessions.map((session) => <div className={`session-row${session.id === activeSessionId ? ' active' : ''}`} key={session.id}>
          <button className="session-select" type="button" onClick={() => selectSession(session.id)} title={session.title}>{session.title}</button>
          <button className="session-delete" type="button" onClick={(event) => removeSession(event, session.id)} aria-label={`Delete ${session.title}`} title="Delete session"><span aria-hidden="true">×</span></button>
        </div>)}
      </div>
      <div className="sidebar-footer">
        <div className="sidebar-footer-heading">Conversation actions</div>
        <button className="sidebar-action sidebar-delete-action" type="button" onClick={deleteAllChats} disabled={!sessions.length}><ControlIcon name="trash" /><span>Delete chat</span></button>
        <div className="sidebar-footer-heading sidebar-appearance-heading">Appearance</div>
        <button className="sidebar-action" type="button" onClick={() => setIsDark((current) => !current)}><ControlIcon name={isDark ? 'sun' : 'moon'} /><span>{isDark ? 'Light mode' : 'Dark mode'}</span></button>
      </div>
      <div className="sidebar-resize-handle" role="separator" aria-label="Resize sidebar" onPointerDown={startSidebarResize} />
    </aside>
    <div className={`chat-panel${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}><ChatCore suggestedQuestions={suggestedQuestions} activeSessionId={activeSessionId} history={history} onSessionCreated={handleSessionCreated} /></div>
  </section></main>
}

export default PageShell