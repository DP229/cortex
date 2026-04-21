import { useState, useEffect } from 'react'
import { Plus, Trash2, Search } from 'lucide-react'
import './MemoryPage.css'

interface MemoryEntry {
  id: string
  content: string
  entry_type: string
  importance: number
}

export default function MemoryPage() {
  const [entries, setEntries] = useState<MemoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [newContent, setNewContent] = useState('')
  const [newType, setNewType] = useState('fact')
  const [newImportance, setNewImportance] = useState(0.5)

  const load = () => {
    fetch('/api/memory/stats')
      .then(r => r.json())
      .then(() => setLoading(false))
      .catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const searchMem = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    try {
      const res = await fetch('/api/memory/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit: 20 }),
      })
      const data = await res.json()
      setEntries(data.results ?? [])
    } catch { setEntries([]) }
  }

  const addMemory = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newContent.trim()) return
    try {
      await fetch('/api/memory/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: newContent, entry_type: newType, importance: newImportance }),
      })
      setNewContent('')
      load()
    } catch {}
  }

  const clearAll = async () => {
    if (!confirm('Clear all memories?')) return
    try {
      await fetch('/api/memory/clear', { method: 'POST' })
      setEntries([])
    } catch {}
  }

  const impColour = (v: number) => v > 0.7 ? 'var(--green)' : v > 0.4 ? 'var(--amber)' : 'var(--red)'

  return (
    <div className="memory-page">
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Memory</h1>
          <p>Long-term memory store for the Cortex agent.</p>
        </div>
        <button className="btn btn-danger" onClick={clearAll}><Trash2 size={14} /> Clear All</button>
      </div>

      {/* Search */}
      <form onSubmit={searchMem} className="mem-search-row">
        <input className="input" placeholder="Search memories…" value={query} onChange={e => setQuery(e.target.value)} />
        <button type="submit" className="btn btn-ghost"><Search size={14} /> Search</button>
      </form>

      {/* Add new */}
      <form onSubmit={addMemory} className="card add-form">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Add Memory</h3>
        <div className="add-form__fields">
          <input
            className="input"
            placeholder="Memory content…"
            value={newContent}
            onChange={e => setNewContent(e.target.value)}
          />
          <select className="input" value={newType} onChange={e => setNewType(e.target.value)}>
            <option value="fact">fact</option>
            <option value="preference">preference</option>
            <option value="context">context</option>
          </select>
          <input
            type="number"
            className="input"
            min="0"
            max="1"
            step="0.1"
            value={newImportance}
            onChange={e => setNewImportance(parseFloat(e.target.value))}
            title="Importance 0–1"
          />
          <button type="submit" className="btn btn-primary"><Plus size={14} /> Add</button>
        </div>
      </form>

      {/* Results */}
      <div className="card">
        <div className="card-header"><h2>Memory Entries</h2></div>
        {loading
          ? <p className="text-muted text-sm">Loading…</p>
          : entries.length === 0
          ? <p className="text-muted text-sm">No entries. Add one above or search.</p>
          : (
            <div className="mem-list">
              {entries.map(e => (
                <div key={e.id} className="mem-entry">
                  <div className="mem-entry__bar" style={{ background: impColour(e.importance) }} />
                  <div className="mem-entry__body">
                    <p className="mem-entry__content">{e.content}</p>
                    <div className="mem-entry__meta">
                      <span className="badge badge-purple">{e.entry_type}</span>
                      <span className="text-muted text-sm">importance: {e.importance.toFixed(1)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        }
      </div>
    </div>
  )
}