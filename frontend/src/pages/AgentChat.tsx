import { useState, useRef, useEffect } from 'react'
import { Send, Trash2 } from 'lucide-react'
import './AgentChat.css'

interface Message {
  role: 'user' | 'assistant'
  content: string
  time: string
}

export default function AgentChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [model, setModel] = useState('llama3')
  const [memoryEnabled, setMemoryEnabled] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMsg: Message = { role: 'user', content: input.trim(), time: new Date().toLocaleTimeString() }
    setMessages(m => [...m, userMsg])
    setInput('')
    setLoading(true)

    try {
      // Ensure agent exists
      await fetch('/api/agent/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'cortex-agent', model, instructions: 'You are a helpful compliance assistant.', memory_enabled: memoryEnabled }),
      }).catch(() => {})

      const res = await fetch('/api/agent/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userMsg.content, model }),
      })

      if (res.ok) {
        const data = await res.json()
        setMessages(m => [...m, {
          role: 'assistant',
          content: data.content ?? 'No response.',
          time: new Date().toLocaleTimeString(),
        }])
      } else {
        setMessages(m => [...m, { role: 'assistant', content: 'Error: could not reach Cortex API. Is the backend running?', time: new Date().toLocaleTimeString() }])
      }
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'Error: could not reach Cortex API. Is the backend running?', time: new Date().toLocaleTimeString() }])
    } finally {
      setLoading(false)
    }
  }

  const reset = () => setMessages([])

  return (
    <div className="agent-chat">
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Agent Chat</h1>
          <p>Query the Cortex compliance agent with memory context.</p>
        </div>
        <div className="flex gap-8 items-center">
          <label className="flex gap-6 items-center text-sm">
            <span>🧠</span> Memory
            <input type="checkbox" checked={memoryEnabled} onChange={e => setMemoryEnabled(e.target.checked)} />
          </label>
          <select className="input" value={model} onChange={e => setModel(e.target.value)}>
            <option value="llama3">llama3</option>
            <option value="mistral">mistral</option>
            <option value="mixtral">mixtral</option>
          </select>
          <button className="btn btn-ghost" onClick={reset}><Trash2 size={14} /> Clear</button>
        </div>
      </div>

      {/* Chat messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p className="text-muted">Send a message to start the agent conversation.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message chat-message--${msg.role}`}>
            <div className="chat-bubble">{msg.content}</div>
            <span className="chat-time">{msg.time}</span>
          </div>
        ))}
        {loading && <div className="chat-message chat-message--assistant"><div className="chat-bubble loading">Thinking…</div></div>}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form className="chat-input-bar" onSubmit={send}>
        <input
          className="input chat-input"
          placeholder="Ask anything…"
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
          autoFocus
        />
        <button type="submit" className="btn btn-primary" disabled={loading || !input.trim()}>
          <Send size={15} /> Send
        </button>
      </form>
    </div>
  )
}