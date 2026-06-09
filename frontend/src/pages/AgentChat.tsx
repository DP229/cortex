import { useState, useEffect, useRef } from 'react'
import { Send, Sparkles, ShieldCheck, HelpCircle, FileText, ChevronRight, Info } from 'lucide-react'
import { api } from '../utils/api'
import './AgentChat.css'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
}

interface Source {
  id: string
  title: string
  category: string
  source?: string
}

const SUGGESTIONS = [
  { label: 'Check requirement SIL alignment', prompt: 'What are the software design rules and architecture constraints for a SIL4 railway system under EN 50128?' },
  { label: 'Draft EN 50128 safety plan', prompt: 'Draft a template for an EN 50128 software safety plan. What sections are required for Class B compliance?' },
  { label: 'Verify SOUP safety justification', prompt: 'How do I justify using a SOUP (Software of Unknown Provenance) component under EN 50128 §6.2? What documents are needed?' },
  { label: 'Review IEC 62443 security rules', prompt: 'Explain the threat modeling and security requirement specifications required for railway automation under IEC 62443.' },
]

export default function AgentChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: "Hello! I'm **Cortex AI**, your railway software safety and compliance copilot. I can assist with **EN 50128 / EN 50716** processes, safety integrity levels (SIL), **IEC 62443** cybersecurity, and tracing requirements to standards.\n\nAsk me a compliance question or select one of the suggestions below to get started!",
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeSources, setActiveSources] = useState<Source[]>([])
  
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async (textToSend: string) => {
    if (!textToSend.trim() || loading) return
    setError('')
    setLoading(true)

    const userMessage: Message = { role: 'user', content: textToSend }
    const currentMessages = [...messages, userMessage]
    
    // Optimistically add user message and clear input
    setMessages(currentMessages)
    setInput('')

    try {
      // Map history without sources
      const historyPayload = messages.map(m => ({
        role: m.role,
        content: m.content
      }))

      const response = await api.post('/chat', {
        message: textToSend,
        history: historyPayload
      })

      const botMessage: Message = {
        role: 'assistant',
        content: response.response,
        sources: response.sources
      }

      setMessages(prev => [...prev, botMessage])
      if (response.sources && response.sources.length > 0) {
        setActiveSources(response.sources)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to communicate with compliance assistant.')
    } finally {
      setLoading(false)
    }
  }

  const selectMessageSources = (sources?: Source[]) => {
    if (sources && sources.length > 0) {
      setActiveSources(sources)
    }
  }

  // A basic helper to safely parse markdown-like structures to React
  const renderMarkdown = (text: string) => {
    const lines = text.split('\n')
    let insideCodeBlock = false
    let codeBlockContent: string[] = []

    return lines.map((line, idx) => {
      // Code Block Detection
      if (line.trim().startsWith('```')) {
        if (insideCodeBlock) {
          insideCodeBlock = false
          const content = codeBlockContent.join('\n')
          codeBlockContent = []
          return (
            <pre key={idx} className="chat-code-block">
              <code>{content}</code>
            </pre>
          )
        } else {
          insideCodeBlock = true
          return null
        }
      }

      if (insideCodeBlock) {
        codeBlockContent.push(line)
        return null
      }

      // Check for bullet list item
      if (line.trim().startsWith('* ') || line.trim().startsWith('- ')) {
        const cleanText = line.replace(/^[\s*-]+/, '')
        return (
          <li key={idx} className="chat-list-item">
            {parseInlineFormatting(cleanText)}
          </li>
        )
      }

      // Check for headers
      if (line.trim().startsWith('#')) {
        const match = line.match(/^(#{1,6})\s+(.*)$/)
        if (match) {
          const level = match[1].length
          const title = match[2]
          if (level === 1) return <h1 key={idx} className="chat-h1">{parseInlineFormatting(title)}</h1>
          if (level === 2) return <h2 key={idx} className="chat-h2">{parseInlineFormatting(title)}</h2>
          return <h3 key={idx} className="chat-h3">{parseInlineFormatting(title)}</h3>
        }
      }

      // Default paragraph
      if (line.trim() === '') return <div key={idx} style={{ height: '8px' }} />
      return <p key={idx} className="chat-p">{parseInlineFormatting(line)}</p>
    })
  }

  // Formats bold (**) and inline code (`)
  const parseInlineFormatting = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g)
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={index}>{part.slice(2, -2)}</strong>
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={index} className="chat-inline-code">{part.slice(1, -1)}</code>
      }
      return part
    })
  }

  return (
    <div className="agent-chat-container">
      <div className="chat-main-panel">
        <div className="page-header flex justify-between items-center">
          <div>
            <h1>AI Compliance Assistant</h1>
            <p>Direct query access to standards-backed knowledge engine with Merkle integrity tracking.</p>
          </div>
          <div className="compliance-shield flex items-center gap-8 badge badge-cyan">
            <ShieldCheck size={14} /> EN 50128 Class B Active
          </div>
        </div>

        {error && <div className="alert-error mb-16">{error}</div>}

        <div className="messages-container">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`message-row ${m.role}`}
              onClick={() => selectMessageSources(m.sources)}
              style={{ cursor: m.sources && m.sources.length > 0 ? 'pointer' : 'default' }}
            >
              <div className="message-avatar">
                {m.role === 'user' ? '👤' : '🤖'}
              </div>
              <div className="message-bubble">
                <div className="message-content">
                  {renderMarkdown(m.content)}
                </div>
                {m.sources && m.sources.length > 0 && (
                  <div className="message-citations-pill">
                    <Info size={11} /> {m.sources.length} compliance citation(s) available
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="message-row assistant loading">
              <div className="message-avatar">🤖</div>
              <div className="message-bubble">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {messages.length === 1 && !loading && (
          <div className="suggestions-grid mb-24">
            <h4 className="suggestion-title">Select a query template:</h4>
            <div className="suggestions-row">
              {SUGGESTIONS.map((s, idx) => (
                <button key={idx} className="suggestion-card" onClick={() => handleSend(s.prompt)}>
                  <span className="suggestion-card-label">{s.label}</span>
                  <ChevronRight size={14} className="suggestion-card-arrow" />
                </button>
              ))}
            </div>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSend(input)
          }}
          className="chat-input-bar"
        >
          <div className="input-wrap">
            <Sparkles size={16} className="sparkles-icon" />
            <input
              className="chat-input"
              placeholder="Ask a compliance or safety standard question..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="btn btn-primary btn-send" disabled={loading || !input.trim()}>
              <Send size={14} /> Send
            </button>
          </div>
        </form>
      </div>

      <div className="chat-sources-sidebar">
        <div className="sidebar-header">
          <HelpCircle size={16} className="sidebar-icon" />
          <h3>Compliance Sources</h3>
        </div>
        <div className="sidebar-body">
          {activeSources.length === 0 ? (
            <div className="empty-sources">
              <Info size={24} className="text-muted" style={{ marginBottom: 12 }} />
              <p className="text-muted text-sm">No citations selected.</p>
              <p className="text-muted text-xs" style={{ marginTop: 8 }}>
                When the compliance agent references standard articles from the Knowledge Base, they will appear here.
              </p>
            </div>
          ) : (
            <div className="sources-list">
              <p className="text-xs text-muted mb-12">RETRIEVED FROM COMPLIANCE DATABASE:</p>
              {activeSources.map((s) => (
                <div key={s.id} className="source-card">
                  <div className="source-badge">
                    <span className="badge badge-purple">{s.category}</span>
                  </div>
                  <h4 className="source-title">{s.title}</h4>
                  {s.source && (
                    <div className="source-reference flex items-center gap-8 text-sm mt-8">
                      <FileText size={12} />
                      <code>{s.source}</code>
                    </div>
                  )}
                  <a href="/kb" className="source-link text-xs">
                    View in Knowledge Base <ChevronRight size={10} />
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
