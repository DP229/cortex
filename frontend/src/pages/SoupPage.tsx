import { useState, useEffect } from 'react'
import { Plus, Search, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'
import { api } from '../utils/api'
import './SoupPage.css'

interface SOUP {
  id: string
  name: string
  vendor?: string
  version: string
  previous_version?: string
  download_url?: string
  checksum?: string
  license_type?: string
  status: string
  safety_relevance: string
  justification?: string
  integration_notes?: string
  approved_by?: string
  approved_at?: string
  review_due_date?: string
  risk_assessment?: string
  created_at: string
}

const STATUS_COLORS: Record<string, string> = {
  candidate: 'badge-amber', approved: 'badge-green', rejected: 'badge-red', under_evaluation: 'badge-purple',
}

export default function SoupPage() {
  const [soups, setSoups] = useState<SOUP[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [selectedSoup, setSelectedSoup] = useState<SOUP | null>(null)
  const [showApproveModal, setShowApproveModal] = useState(false)
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [actionJustification, setActionJustification] = useState('')
  const [form, setForm] = useState({
    name: '', vendor: '', version: '', previous_version: '', download_url: '',
    checksum: '', license_type: '', safety_relevance: 'class_b', justification: '',
    integration_notes: '', risk_assessment: '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => { loadSoups() }, [])

  const loadSoups = async () => {
    setLoading(true)
    try {
      const data = await api.get('/v1/soups')
      setSoups(Array.isArray(data) ? data : (data.soups ?? []))
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const filtered = soups.filter(s => {
    if (search && !s.name.toLowerCase().includes(search.toLowerCase()) && !s.vendor?.toLowerCase().includes(search.toLowerCase())) return false
    if (statusFilter && s.status !== statusFilter) return false
    return true
  })

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload: any = { ...form }
      if (!payload.vendor) delete payload.vendor
      if (!payload.previous_version) delete payload.previous_version
      if (!payload.download_url) delete payload.download_url
      if (!payload.checksum) delete payload.checksum
      if (!payload.license_type) delete payload.license_type
      if (!payload.justification) delete payload.justification
      if (!payload.integration_notes) delete payload.integration_notes
      if (!payload.risk_assessment) delete payload.risk_assessment
      await api.post('/v1/soups', payload)
      setShowModal(false)
      setForm({ name: '', vendor: '', version: '', previous_version: '', download_url: '', checksum: '', license_type: '', safety_relevance: 'class_b', justification: '', integration_notes: '', risk_assessment: '' })
      loadSoups()
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  const handleApprove = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedSoup) return
    setSaving(true)
    try {
      await api.post(`/v1/soups/${selectedSoup.id}/approve`, { justification: actionJustification })
      setShowApproveModal(false)
      setActionJustification('')
      loadSoups()
      setSelectedSoup(null)
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  const handleReject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedSoup) return
    setSaving(true)
    try {
      await api.post(`/v1/soups/${selectedSoup.id}/reject`, { justification: actionJustification })
      setShowRejectModal(false)
      setActionJustification('')
      loadSoups()
      setSelectedSoup(null)
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  return (
    <div className="soup-page">
      <div className="page-header">
        <h1>SOUP Management</h1>
        <p>EN 50128 §4.2 — Software of Unknown Provenance register</p>
      </div>

      <div className="flex justify-between items-center gap-12 mb-24">
        <div className="flex gap-8" style={{ flex: 1, maxWidth: 500 }}>
          <div className="search-bar" style={{ flex: 1 }}>
            <Search size={16} className="search-icon" />
            <input className="input search-input" placeholder="Search by name or vendor…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ width: 150 }}>
            <option value="">All Status</option>
            {['candidate', 'under_evaluation', 'approved', 'rejected'].map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={16} /> Register SOUP
        </button>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th><th>Vendor</th><th>Version</th><th>License</th>
                <th>Status</th><th>Safety Class</th><th>Review Due</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="text-muted text-sm">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={7} className="text-muted text-sm">No SOUPs found. Register your first SOUP.</td></tr>
              ) : filtered.map(soup => (
                <tr key={soup.id} className="clickable-row" onClick={() => setSelectedSoup(soup)}>
                  <td><strong>{soup.name}</strong></td>
                  <td className="text-muted text-sm">{soup.vendor || '—'}</td>
                  <td><code style={{ fontSize: 12 }}>{soup.version}</code></td>
                  <td className="text-muted text-sm">{soup.license_type || '—'}</td>
                  <td><span className={`badge ${STATUS_COLORS[soup.status]}`}>{soup.status.replace('_', ' ')}</span></td>
                  <td><span className="badge badge-purple">{soup.safety_relevance}</span></td>
                  <td className="text-muted text-sm">
                    {soup.review_due_date ? new Date(soup.review_due_date).toLocaleDateString() : '—'}
                    {soup.review_due_date && new Date(soup.review_due_date) < new Date() && (
                      <AlertTriangle size={12} style={{ color: 'var(--red)', marginLeft: 4 }} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedSoup && (
        <div className="modal-overlay" onClick={() => setSelectedSoup(null)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{selectedSoup.name}</h3>
                <code style={{ fontSize: 11, color: 'var(--text-muted)' }}>v{selectedSoup.version}</code>
              </div>
              <button className="btn btn-ghost" onClick={() => setSelectedSoup(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div><label>Status</label><span className={`badge ${STATUS_COLORS[selectedSoup.status]}`}>{selectedSoup.status}</span></div>
                <div><label>Vendor</label><span>{selectedSoup.vendor || '—'}</span></div>
                <div><label>License</label><span>{selectedSoup.license_type || '—'}</span></div>
                <div><label>Safety Class</label><span>{selectedSoup.safety_relevance}</span></div>
                <div><label>Created</label><span>{new Date(selectedSoup.created_at).toLocaleString()}</span></div>
                {selectedSoup.approved_at && <div><label>Approved</label><span>{new Date(selectedSoup.approved_at).toLocaleString()}</span></div>}
                {selectedSoup.review_due_date && <div><label>Review Due</label><span style={{ color: new Date(selectedSoup.review_due_date) < new Date() ? 'var(--red)' : undefined }}>{new Date(selectedSoup.review_due_date).toLocaleDateString()}</span></div>}
              </div>
              {selectedSoup.download_url && (
                <div style={{ marginTop: 12 }}>
                  <label>Download URL</label>
                  <a href={selectedSoup.download_url} target="_blank" rel="noopener noreferrer" className="text-sm text-accent">{selectedSoup.download_url}</a>
                </div>
              )}
              {selectedSoup.checksum && <div style={{ marginTop: 8 }}><label>SHA-256 Checksum</label><code style={{ fontSize: 11 }}>{selectedSoup.checksum}</code></div>}
              {selectedSoup.justification && <div style={{ marginTop: 16 }}><label>Justification</label><p className="text-sm" style={{ marginTop: 4 }}>{selectedSoup.justification}</p></div>}
              {selectedSoup.integration_notes && <div style={{ marginTop: 12 }}><label>Integration Notes</label><p className="text-sm" style={{ marginTop: 4 }}>{selectedSoup.integration_notes}</p></div>}
              {selectedSoup.risk_assessment && <div style={{ marginTop: 12 }}><label>Risk Assessment</label><p className="text-sm" style={{ marginTop: 4 }}>{selectedSoup.risk_assessment}</p></div>}
            </div>
            <div className="modal-footer">
              {selectedSoup.status === 'candidate' && (
                <>
                  <button className="btn btn-primary" onClick={() => setShowApproveModal(true)}><CheckCircle size={14} /> Approve SOUP</button>
                  <button className="btn btn-danger" onClick={() => setShowRejectModal(true)}><XCircle size={14} /> Reject</button>
                </>
              )}
              <button className="btn btn-ghost" onClick={() => setSelectedSoup(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {showApproveModal && selectedSoup && (
        <div className="modal-overlay" onClick={() => setShowApproveModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>Approve SOUP: {selectedSoup.name}</h3><button className="btn btn-ghost" onClick={() => setShowApproveModal(false)}>✕</button></div>
            <form onSubmit={handleApprove}>
              <div className="modal-body">
                <p className="text-sm text-muted mb-16">EN 50128 §4.2 requires documented justification for SOUP approval. Provide the safety rationale.</p>
                <div className="form-group">
                  <label>Justification *</label>
                  <textarea className="input" rows={4} placeholder="Why is this SOUP acceptable for the safety function?" value={actionJustification} onChange={e => setActionJustification(e.target.value)} required />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowApproveModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Approving…' : 'Confirm Approval'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showRejectModal && selectedSoup && (
        <div className="modal-overlay" onClick={() => setShowRejectModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>Reject SOUP: {selectedSoup.name}</h3><button className="btn btn-ghost" onClick={() => setShowRejectModal(false)}>✕</button></div>
            <form onSubmit={handleReject}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Reason for Rejection *</label>
                  <textarea className="input" rows={4} placeholder="Why is this SOUP not acceptable?" value={actionJustification} onChange={e => setActionJustification(e.target.value)} required />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowRejectModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-danger" disabled={saving}>{saving ? 'Rejecting…' : 'Confirm Rejection'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>Register SOUP</h3><button className="btn btn-ghost" onClick={() => setShowModal(false)}>✕</button></div>
            <form onSubmit={handleCreate}>
              <div className="modal-body">
                {error && <div className="alert-error mb-16">{error}</div>}
                <div className="form-grid">
                  <div className="form-group"><label>Name *</label><input className="input" placeholder="SOUP name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required /></div>
                  <div className="form-group"><label>Vendor</label><input className="input" placeholder="Vendor name" value={form.vendor} onChange={e => setForm({ ...form, vendor: e.target.value })} /></div>
                  <div className="form-group"><label>Version *</label><input className="input" placeholder="e.g., 2.1.0" value={form.version} onChange={e => setForm({ ...form, version: e.target.value })} required /></div>
                  <div className="form-group"><label>Previous Version</label><input className="input" placeholder="If upgrading" value={form.previous_version} onChange={e => setForm({ ...form, previous_version: e.target.value })} /></div>
                  <div className="form-group"><label>Download URL</label><input className="input" type="url" placeholder="https://…" value={form.download_url} onChange={e => setForm({ ...form, download_url: e.target.value })} /></div>
                  <div className="form-group"><label>SHA-256 Checksum</label><input className="input" placeholder="64-char hex" value={form.checksum} onChange={e => setForm({ ...form, checksum: e.target.value })} /></div>
                  <div className="form-group"><label>License Type</label><input className="input" placeholder="e.g., Apache-2.0" value={form.license_type} onChange={e => setForm({ ...form, license_type: e.target.value })} /></div>
                  <div className="form-group">
                    <label>Safety Relevance</label>
                    <select className="input" value={form.safety_relevance} onChange={e => setForm({ ...form, safety_relevance: e.target.value })}>
                      {['class_a', 'class_b', 'class_c'].map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}><label>Justification</label><textarea className="input" rows={2} placeholder="Why is this SOUP acceptable?" value={form.justification} onChange={e => setForm({ ...form, justification: e.target.value })} /></div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}><label>Integration Notes</label><textarea className="input" rows={2} placeholder="How is it integrated?" value={form.integration_notes} onChange={e => setForm({ ...form, integration_notes: e.target.value })} /></div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}><label>Risk Assessment</label><textarea className="input" rows={2} placeholder="Known failure modes, mitigations" value={form.risk_assessment} onChange={e => setForm({ ...form, risk_assessment: e.target.value })} /></div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Registering…' : 'Register SOUP'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
