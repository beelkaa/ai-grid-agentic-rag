import { useEffect, useRef, useState } from 'react'
import { marked } from 'marked'
import markedKatex from 'marked-katex-extension'
import 'katex/dist/katex.min.css'
import '../App.css'

marked.use(markedKatex({ throwOnError: false }))

const documentationSuggestions = [
  { label: 'Chat & agents', question: 'How do I build a chat assistant or agent with AI GRID?' },
  { label: 'Search & RAG', question: 'How do AI GRID embeddings work for semantic search and RAG?' },
  { label: 'OCR & documents', question: 'How can I use AI GRID for OCR and document processing?' },
  { label: 'API security', question: 'What is the recommended secure way to integrate the AI GRID API?' },
]

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
    <button type="button" onClick={() => onRetry(message.question)} aria-label="Try again" title="Try again"><span>↻</span></button>
    {!message.interrupted && <button type="button" onClick={copyResponse} aria-label="Copy response" title={copied ? 'Copied' : 'Copy response'}><span className={copied ? 'copied-icon' : 'copy-glyph'}>{copied ? '✓' : ''}</span></button>}
  </div>
}

function ChatCore({ activeSessionId = null, history = null, onSessionCreated, headerActions = null }) {
  const [question, setQuestion] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([{ role: 'assistant', content: 'Hello. I am the AI GRID Assistant. How can I help you explore the documentation?' }])
  const abortController = useRef(null)
  const skipSessionNotification = useRef(false)
  useEffect(() => {
    if (history === null) return
    skipSessionNotification.current = true
    setSessionId(activeSessionId)
    setMessages(history.length ? history : [{ role: 'assistant', content: 'Hello. I am the AI GRID Assistant. How can I help you explore the documentation?' }])
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
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        if (!chunk) continue
        answer += chunk
        if (!hasStartedStreaming) {
          hasStartedStreaming = true
          setIsThinking(false)
          setMessages((currentMessages) => [...currentMessages, { id: messageId, role: 'assistant', content: answer, question: trimmedQuestion }])
        } else {
          setMessages((currentMessages) => currentMessages.map((message) => message.id === messageId ? { ...message, content: answer } : message))
        }
      }
      const trailingChunk = decoder.decode()
      if (trailingChunk) {
        answer += trailingChunk
        setMessages((currentMessages) => currentMessages.map((message) => message.id === messageId ? { ...message, content: answer } : message))
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
  return <>
    <header className="window-header"><div className="identity"><BrandMark /><div><h1>AI GRID Assistant</h1><p><span className="status-dot" /> Ready when you are</p></div></div>{headerActions && <div className="window-controls">{headerActions}</div>}</header>
    <div className="conversation" aria-live="polite">
      <div className="conversation-intro"><span className="intro-line" /><span>AI GRID DOCUMENTATION</span><span className="intro-line" /></div>
      {messages.map((message, index) => <article className={`message ${message.role}`} key={message.id || `${message.role}-${index}`}>
        {message.role === 'assistant' && <BrandMark small />}
        {message.role === 'user' ? <div className="question-bubble">{message.content}</div> : <div className={`answer${message.error || message.interrupted ? ' error' : ''}`}><Markdown content={message.content} />{message.complete && message.question && <><div className="answer-meta">{message.interrupted ? 'Response interrupted' : `Responded in ${message.responseTime || '--'}s`}</div><ResponseActions message={message} onRetry={(retryQuestion) => sendQuestion(null, retryQuestion)} /></>}</div>}
      </article>)}
      {isThinking && <div className="thinking-row"><BrandMark small /><div className="thinking"><span /><span /><span /><b>Thinking</b></div></div>}
      {messages.length === 1 && !isThinking && <div className="documentation-suggestions"><div className="suggestions-label">Explore AI GRID documentation</div><div className="suggestions-grid">{documentationSuggestions.map((suggestion) => <button type="button" key={suggestion.label} onClick={() => sendQuestion(null, suggestion.question)}><span>{suggestion.label}</span><b>→</b></button>)}</div></div>}
    </div>
    <form className="composer" onSubmit={sendQuestion}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={handleKeyDown} placeholder="Ask AI GRID Assistant..." rows="1" aria-label="Ask AI GRID Assistant" />{isThinking ? <button className="composer-action stop" type="button" onClick={stopQuestion} aria-label="Stop response" title="Stop response"><span /></button> : <button className="composer-action send" type="submit" disabled={!question.trim()} aria-label="Send message" title="Send message">↑</button>}<div className="composer-note"><span>Based on AI GRID documentation, AI may make mistakes.</span><kbd>Enter</kbd></div></form>
  </>
}

export default ChatCore