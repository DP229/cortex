import { useState, useEffect } from 'react'
import { Plus, Search, Tag, Trash2, X } from 'lucide-react'
import { api } from '../utils/api'
import './KnowledgeBase.css'

interface Article {
  id: string
  title: string
  content: string
  category: string
  tags: string[]
  status: string
  source?: string
  references?: string[]
  created_at: string
}

const CATEGORIES = ['standard', 'regulation', 'guideline', 'best_practice', 'railway_domain', 'security']

export default function KnowledgeBase() {
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [selected, setSelected] = useState<Article | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ title: '', content: '', category: 'standard', tags: '', source: '', references: '' })

  useEffect(() => { loadArticles() }, [])

  const loadArticles = async () => {
    setLoading(true)
    try {
      const data = await api.get('/kb/articles?limit=200')
      setArticles(Array.isArray(data) ? data : (data.articles ?? []))
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const filtered = articles.filter(a => {
    if (search && !a.title.toLowerCase().includes(search.toLowerCase()) && !a.content.toLowerCase().includes(search.toLowerCase())) return false
    if (categoryFilter && a.category !== categoryFilter) return false
    return true
  })

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const tagList = form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : undefined
      const refList = form.references ? form.references.split(',').map(r => r.trim()).filter(Boolean) : undefined
      const payload: any = { title: form.title, content: form.content, category: form.category }
      if (tagList) payload.tags = tagList
      if (form.source) payload.source = form.source
      if (refList) payload.references = refList
      await api.post('/kb/articles', payload)
      setShowModal(false)
      setForm({ title: '', content: '', category: 'standard', tags: '', source: '', references: '' })
      loadArticles()
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.del(`/kb/articles/${id}`)
      loadArticles()
      if (selected?.id === id) setSelected(null)
    } catch (e: any) { setError(e.message) }
  }

  return (
    <div className="kb">
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Knowledge Base</h1>
          <p>Railway safety standards, regulations, and domain knowledge. Inject knowledge for compliance.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={14} /> Inject Knowledge</button>
      </div>

      <div className="kb-toolbar">
        <div className="flex gap-8" style={{ flex: 1 }}>
          <div className="search-bar" style={{ flex: 1 }}>
            <Search size={16} className="search-icon" />
            <input className="input search-input" placeholder="Search articles…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>
        <div className="kb-filters">
          <button className={`badge ${categoryFilter === null ? 'badge-purple' : 'badge-ghost'}`} onClick={() => setCategoryFilter(null)}>All</button>
          {CATEGORIES.map(c => (
            <button key={c} className={`badge ${categoryFilter === c ? 'badge-purple' : 'badge-ghost'}`}
              onClick={() => setCategoryFilter(c === categoryFilter ? null : c)}>{c.replace('_', ' ')}</button>
          ))}
        </div>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : filtered.length === 0 ? (
        <div className="card"><p className="text-muted text-sm">No articles found. Inject your first piece of knowledge.</p></div>
      ) : (
        <div className="kb-list">
          {filtered.map(a => (
            <div key={a.id} className="card kb-entry" onClick={() => setSelected(a)} style={{ cursor: 'pointer' }}>
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="kb-entry-title">{a.title}</h3>
                  <p className="kb-entry-text">{a.content.slice(0, 200)}{a.content.length > 200 ? '…' : ''}</p>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); handleDelete(a.id) }} title="Delete">
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="kb-entry-footer">
                <span className="badge badge-amber">{a.category.replace('_', ' ')}</span>
                {a.source && <span className="text-muted text-sm">Source: {a.source}</span>}
                <div className="kb-tags">
                  {(a.tags ?? []).map(t => <span key={t} className="kb-tag"><Tag size={10} /> {t}</span>)}
                </div>
                <span className="text-muted text-sm" style={{ marginLeft: 'auto' }}>{a.created_at?.slice(0, 10)}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{selected.title}</h3>
                <span className="badge badge-amber">{selected.category.replace('_', ' ')}</span>
              </div>
              <button className="btn btn-ghost" onClick={() => setSelected(null)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div><label>Status</label><span>{selected.status}</span></div>
                {selected.source && <div><label>Source</label><span>{selected.source}</span></div>}
                <div><label>Created</label><span>{new Date(selected.created_at).toLocaleString()}</span></div>
              </div>
              <div style={{ marginTop: 12 }}>
                <label>Tags</label>
                <div className="kb-tags">{(selected.tags ?? []).map(t => <span key={t} className="kb-tag"><Tag size={10} /> {t}</span>)}</div>
              </div>
              <div style={{ marginTop: 16, whiteSpace: 'pre-wrap' }}>
                <label>Content</label>
                <p className="text-sm" style={{ marginTop: 4 }}>{selected.content}</p>
              </div>
              {selected.references && selected.references.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <label>References</label>
                  <ul className="text-sm" style={{ marginTop: 4, paddingLeft: 16 }}>
                    {selected.references.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setSelected(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>Inject Knowledge</h3><button className="btn btn-ghost" onClick={() => setShowModal(false)}><X size={16} /></button></div>
            <form onSubmit={handleCreate}>
              <div className="modal-body">
                {error && <div className="alert-error mb-16">{error}</div>}
                <div className="form-grid">
                  <div className="form-group"><label>Title *</label><input className="input" placeholder="Article title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required /></div>
                  <div className="form-group">
                    <label>Category *</label>
                    <select className="input" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                      {CATEGORIES.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
                    </select>
                  </div>
                  <div className="form-group"><label>Source</label><input className="input" placeholder="e.g., EN 50128:2011 §6.2" value={form.source} onChange={e => setForm({ ...form, source: e.target.value })} /></div>
                  <div className="form-group"><label>Tags (comma-separated)</label><input className="input" placeholder="SIL, interlocking, signalling" value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} /></div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}><label>Content *</label><textarea className="input" rows={6} placeholder="Knowledge content…" value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} required /></div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}><label>References (comma-separated)</label><input className="input" placeholder="EN50128, IEC61508, ISO9001" value={form.references} onChange={e => setForm({ ...form, references: e.target.value })} /></div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save Knowledge'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
