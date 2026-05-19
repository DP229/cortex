import { useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import { api } from '../utils/api'
import './DocumentsPage.css'

interface Document {
  id: string; filename: string; title: string; document_type: string
  file_type: string; file_size: number; checksum: string; current_version: number
  status: string; uploaded_by: string; asset_id?: string; created_at: string
  updated_at?: string; retention_until?: string; tags?: string[]
}

const TYPE_COLORS: Record<string, string> = {
  safety_plan: 'badge-red', software_requirements: 'badge-amber', design_specification: 'badge-purple',
  verification_report: 'badge-green', audit_report: 'badge-green', incident_report: 'badge-red', other: 'badge-purple',
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Document | null>(null)

  useEffect(() => { loadDocs() }, [])

  const loadDocs = async () => {
    setLoading(true)
    try {
      const data = await api.get('/documents')
      const items = data.documents ?? (Array.isArray(data) ? data : [])
      setDocs(items)
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const filtered = docs.filter(d => {
    if (search && !d.title?.toLowerCase().includes(search.toLowerCase()) && !d.filename?.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="documents-page">
      <div className="page-header">
        <h1>Compliance Documents</h1>
        <p>EN 50128 — Railway safety documents with encrypted storage and SHA-256 verification</p>
      </div>

      <div className="flex justify-between items-center gap-12 mb-24">
        <div className="flex gap-8" style={{ flex: 1, maxWidth: 400 }}>
          <div className="search-bar" style={{ flex: 1 }}>
            <Search size={16} className="search-icon" />
            <input className="input search-input" placeholder="Search documents…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Title</th><th>Type</th><th>File</th><th>Size</th><th>Version</th><th>Status</th><th>Retention</th></tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="text-muted text-sm">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={7} className="text-muted text-sm">No documents found.</td></tr>
              ) : filtered.map(d => (
                <tr key={d.id} className="clickable-row" onClick={() => setSelected(d)}>
                  <td><strong>{d.title || d.filename}</strong></td>
                  <td><span className={`badge ${TYPE_COLORS[d.document_type] || 'badge-purple'}`}>{d.document_type?.replace('_', ' ')}</span></td>
                  <td className="text-muted text-sm">{d.filename}</td>
                  <td className="text-muted text-sm">{formatSize(d.file_size)}</td>
                  <td><span className="badge badge-purple">v{d.current_version}</span></td>
                  <td><span className="badge badge-green">{d.status}</span></td>
                  <td className="text-muted text-sm">{d.retention_until ? new Date(d.retention_until).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div><h3>{selected.title || selected.filename}</h3></div>
              <button className="btn btn-ghost" onClick={() => setSelected(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div><label>Type</label><span>{selected.document_type?.replace('_', ' ')}</span></div>
                <div><label>Status</label><span>{selected.status}</span></div>
                <div><label>File</label><span>{selected.filename} ({selected.file_type})</span></div>
                <div><label>Size</label><span>{formatSize(selected.file_size)}</span></div>
                <div><label>Version</label><span>v{selected.current_version}</span></div>
                <div><label>Uploaded</label><span>{new Date(selected.created_at).toLocaleString()}</span></div>
                {selected.updated_at && <div><label>Updated</label><span>{new Date(selected.updated_at).toLocaleString()}</span></div>}
                {selected.retention_until && <div><label>Retention Until</label><span>{new Date(selected.retention_until).toLocaleDateString()}</span></div>}
              </div>
              <div style={{ marginTop: 12 }}><label>SHA-256 Checksum</label><code style={{ fontSize: 10, wordBreak: 'break-all' }}>{selected.checksum}</code></div>
              {selected.tags && selected.tags.length > 0 && (
                <div style={{ marginTop: 12 }}><label>Tags</label><div className="flex gap-4 mt-4">{selected.tags.map(t => <span key={t} className="badge badge-purple">{t}</span>)}</div></div>
              )}
            </div>
            <div className="modal-footer"><button className="btn btn-ghost" onClick={() => setSelected(null)}>Close</button></div>
          </div>
        </div>
      )}
    </div>
  )
}
