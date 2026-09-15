import { useEffect, useRef, useState } from 'react'
import { marked } from 'marked'
import markedKatex from 'marked-katex-extension'
import 'katex/dist/katex.min.css'
import '../App.css'

marked.use(markedKatex({ throwOnError: false }))

function Icon({ name, size = 16 }) {
  const paths = {
    copy: <><rect x="5" y="5" width="7" height="8" rx="1" /><path d="M3 10V3.5a1 1 0 0 1 1-1h5" /></>,
    refresh: <><path d="M12 6a4.5 4.5 0 0 0-7.8-1.3L3 6" /><path d="M3 3.5V6h2.5M4 10a4.5 4.5 0 0 0 7.8 1.3L13 10" /><path d="M13 12.5V10h-2.5" /></>,
    send: <path d="M8 13V3M4.5 6.5 8 3l3.5 3.5" />,
  }
  return <svg className="icon" width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

function BrandMark({ small = false }) {
  return <span className={`brand-mark${small ? ' small' : ''}`} aria-hidden="true"><i /><i /><i /><i /></span>
}

function escapeHtml(value) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;')
}

function Markdown({ content }) {
  const renderer = new marked.Renderer()
  renderer.code = ({ text, lang }) => {
    const language = escapeHtml(lang || 'code')
    return `<div class="code-block"><div class="code-header"><span>${language}</span><button type="button" data-copy-code="${encodeURIComponent(text)}">Copy</button></div><pre><code>${escapeHtml(text)}</code></pre></div>`
  }
  let html
  try {
    html = marked.parse(content.replaceAll('<', '&lt;').replaceAll('>', '&gt;'), { breaks: true, gfm: true, renderer })
  } catch {
    return <div className="markdown markdown-fallback">{content}</div>
  }
  async function copyCode(event) {
    const button = event.target.closest('[data-copy-code]')
    if (!button) return
    await navigator.clipboard.writeText(decodeURIComponent(button.dataset.copyCode))
    button.textContent = 'Copied'
    window.setTimeout(() => { button.textContent = 'Copy' }, 1400)
  }
  return <div className="markdown" onClick={copyCode} dangerouslySetInnerHTML={{ __html: html }} />
}

function ResponseActions({ message, onRetry }) {
  const [copied, setCopied] = useState(false)
  async function copyResponse() {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }
  return <div className="response-actions">
    <button type="button" onClick={() => onRetry(message.question)} aria-label="Try again" title="Try again"><Icon name="refresh" /></button>
    {!message.interrupted && <button type="button" onClick={copyResponse} aria-label="Copy response" title={copied ? 'Copied' : 'Copy response'}><span className={copied ? 'copied-icon' : ''}>{copied ? '✓' : <Icon name="copy" />}</span></button>}
  </div>
}

function Composer({ question, setQuestion, isThinking, sendQuestion, stopQuestion, handleKeyDown, centered = false }) {
  return <form className={`composer${centered ? ' composer-centered' : ' composer-active'}`} onSubmit={sendQuestion}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={handleKeyDown} placeholder="Ask AI GRID Assistant..." rows="1" aria-label="Ask AI GRID Assistant" />{isThinking ? <button className="composer-action stop" type="button" onClick={stopQuestion} aria-label="Stop response" title="Stop response"><span /></button> : <button className="composer-action send" type="submit" disabled={!question.trim()} aria-label="Send message" title="Send message"><Icon name="send" size={17} /></button>}</form>
}

function ChatCore({ activeSessionId = null, history = null, onSessionCreated, headerActions = null }) {
  const [question, setQuestion] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const abortController = useRef(null)
  const skipSessionNotification = useRef(false)
  useEffect(() => {
    if (history === null) return
    skipSessionNotification.current = true
    setSessionId(activeSessionId)
    setMessages(history)
  }, [activeSessionId, history])
  useEffect(() => {
    if (skipSessionNotification.current) {
      skipSessionNotification.current = false
      return
    }
    if (sessionId !== null && sessionId !== activeSessionId) onSessionCreated?.(sessionId)
  }, [activeSessionId, onSessionCreated, sessionId])
  async function sendQuestion(event, retryQuestion = question) {
    event?.preventDefault()
    const trimmedQuestion = retryQuestion.trim()
    if (!trimmedQuestion || isThinking) return
    const controller = new AbortController()
    controller.question = trimmedQuestion
    const startedAt = performance.now()
    abortController.current = controller
    setQuestion('')
    setMessages((currentMessages) => [...currentMessages, { role: 'user', content: trimmedQuestion }])
    setIsThinking(true)
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: trimmedQuestion, session_id: sessionId }),
        signal: controller.signal,
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || `Request failed (${response.status})`)
      }
      const streamedSessionId = response.headers.get('X-Session-Id')
      if (streamedSessionId) setSessionId(Number(streamedSessionId))
      const responseTime = ((performance.now() - startedAt) / 1000).toFixed(1)
      const messageId = `${Date.now()}-assistant`
      if (response.headers.get('content-type')?.includes('application/json')) {
        const data = await response.json()
        if (data.session_id) setSessionId(data.session_id)
        const answer = data.answer || 'I received an empty response.'
        setMessages((currentMessages) => [...currentMessages, { id: messageId, role: 'assistant', content: answer, question: trimmedQuestion, responseTime, complete: true }])
        setIsThinking(false)
        return
      }
      let answer = ''
      let hasStartedStreaming = false
      const reader = response.body?.getReader()
      if (!reader) throw new Error('The response did not include a readable stream.')
      const decoder = new TextDecoder()
      let pendingEvent = ''
      function applyStreamEvent(event) {
        if (!event) return
        const dataLine = event.split('\n').find((line) => line.startsWith('data:'))
        if (!dataLine) return
        let streamEvent
        try {
          streamEvent = JSON.parse(dataLine.slice(5).trim())
        } catch {
          throw new Error('The response stream contained invalid data.')
        }
        if (streamEvent.type === 'replace') answer = streamEvent.text
        else if (streamEvent.type === 'token') answer += streamEvent.text
        else return
        if (!hasStartedStreaming) {
          hasStartedStreaming = true
          setIsThinking(false)
          setMessages((currentMessages) => [...currentMessages, { id: messageId, role: 'assistant', content: answer, question: trimmedQuestion }])
        } else {
          setMessages((currentMessages) => currentMessages.map((message) => message.id === messageId ? { ...message, content: answer } : message))
        }
      }
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        pendingEvent += decoder.decode(value, { stream: true })
        const events = pendingEvent.split('\n\n')
        pendingEvent = events.pop() || ''
        for (const event of events) applyStreamEvent(event)
      }
      pendingEvent += decoder.decode()
      if (pendingEvent.trim()) {
        for (const event of pendingEvent.split('\n\n')) applyStreamEvent(event)
      }
      if (!hasStartedStreaming) {
        answer = 'I received an empty response.'
        setMessages((currentMessages) => [...currentMessages, { id: messageId, role: 'assistant', content: answer, question: trimmedQuestion }])
      }
      setMessages((currentMessages) => currentMessages.map((message) => message.id === messageId ? { ...message, content: answer, responseTime, complete: true } : message))
      setIsThinking(false)
    } catch (error) {
      if (error.name !== 'AbortError') setMessages((currentMessages) => [...currentMessages, { role: 'assistant', error: true, content: `I could not complete that request. ${error.message}` }])
    } finally {
      abortController.current = null
      setIsThinking(false)
    }
  }
  function stopQuestion() {
    const interruptedQuestion = abortController.current?.question
    abortController.current?.abort()
    if (interruptedQuestion) setMessages((currentMessages) => [...currentMessages, { role: 'assistant', interrupted: true, question: interruptedQuestion, complete: true, content: 'You interrupted the response. Try again when you are ready.' }])
    setIsThinking(false)
  }
  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendQuestion(event)
    }
  }
  const isNewChat = messages.length === 0
  return <>
    <div className={`conversation ${isNewChat ? 'is-new-chat' : 'is-active-chat'}`} aria-live="polite">
      <div className="conversation-toolbar">{headerActions && <div className="window-controls">{headerActions}</div>}</div>
      {messages.map((message, index) => <article className={`message ${message.role}`} key={message.id || `${message.role}-${index}`}>
        {message.role === 'assistant' && <BrandMark small />}
        {message.role === 'user' ? <div className="question-bubble">{message.content}</div> : <div className={`answer${message.error || message.interrupted ? ' error' : ''}`}><Markdown content={message.content} />{message.complete && message.question && <><div className="answer-meta">{message.interrupted ? 'Response interrupted' : `Responded in ${message.responseTime || '--'}s`}</div><ResponseActions message={message} onRetry={(retryQuestion) => sendQuestion(null, retryQuestion)} /></>}</div>}
      </article>)}
      {isThinking && <div className="thinking-row"><BrandMark small /><div className="thinking"><span /><span /><span /><b>Thinking</b></div></div>}
      {isNewChat && !isThinking && <><section className="welcome-state" aria-labelledby="welcome-title"><div className="welcome-kicker">AI GRID Assistant</div><h2 id="welcome-title">Ask anything about the AI GRID platform.</h2></section><Composer question={question} setQuestion={setQuestion} isThinking={isThinking} sendQuestion={sendQuestion} stopQuestion={stopQuestion} handleKeyDown={handleKeyDown} centered /></>}
    </div>
    {!isNewChat && <Composer question={question} setQuestion={setQuestion} isThinking={isThinking} sendQuestion={sendQuestion} stopQuestion={stopQuestion} handleKeyDown={handleKeyDown} />}
  </>
}

export default ChatCore