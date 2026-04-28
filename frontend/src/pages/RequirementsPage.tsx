import { useState, useEffect } from 'react'
import { Plus, Search, CheckCircle } from 'lucide-react'
import { api } from '../utils/api'
import './RequirementsPage.css'

interface Requirement {
  id: string
  requirement_id: string
  title: string
  description: string
  priority: string
  status: string
  safety_class: string
  sil_level: string
  category?: string
  verification_method?: string
  verification_status: string
  created_at: string
  approved_at?: string
  citations?: RequirementCitation[]
}

interface RequirementCitation {
  id: string
  citation_type: string
  citation_text?: string
  verified: boolean
  target_requirement_id?: string
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'badge-amber', review: 'badge-amber', approved: 'badge-green',
  verified: 'badge-green', implemented: 'badge-purple', rejected: 'badge-red',
}
const VERIF_COLORS: Record<string, string> = {
  pending: 'badge-amber', passed: 'badge-green', failed: 'badge-red', blocked: 'badge-red', not_applicable: 'badge-purple',
}
const CITATION_TYPES = ['verifies', 'satisfies', 'conflicts_with', 'refines']
const CATEGORIES = ['functional', 'safety', 'security', 'performance']
const SAFETY_CLASSES = ['class_a', 'class_b', 'class_c']
const SIL_LEVELS = ['sil0', 'sil1', 'sil2', 'sil3', 'sil4']

export default function RequirementsPage() {
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [selectedReq, setSelectedReq] = useState<Requirement | null>(null)
  const [showCitationModal, setShowCitationModal] = useState(false)
  const [citationTarget, setCitationTarget] = useState('')
  const [citationType, setCitationType] = useState('verifies')
  const [citationText, setCitationText] = useState('')
  const [form, setForm] = useState({
    requirement_id: '', title: '', description: '', priority: 'shall',
    safety_class: 'class_b', sil_level: 'sil2', category: 'functional',
    verification_method: 'inspection',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => { loadRequirements() }, [])

  const loadRequirements = async () => {
    setLoading(true)
    try {
      const data = await api.get('/v1/requirements')
      setRequirements(Array.isArray(data) ? data : (data.requirements ?? []))
    } catch (e: any) { setError(e.message) }
      finally { setLoading(false) }
  }

  const filtered = requirements.filter(r => {
    if (search && !r.title.toLowerCase().includes(search.toLowerCase()) && !r.requirement_id.toLowerCase().includes(search.toLowerCase())) return false
    if (statusFilter && r.status !== statusFilter) return false
    return true
  })

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post('/v1/requirements', form)
      setShowModal(false)
      setForm({ requirement_id: '', title: '', description: '', priority: 'shall', safety_class: 'class_b', sil_level: 'sil2', category: 'functional', verification_method: 'inspection' })
      loadRequirements()
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  const handleApprove = async (id: string) => {
    try {
      await api.post(`/v1/requirements/${id}/approve`, { justification: 'Approved via UI' })
      loadRequirements()
      if (selectedReq?.id === id) {
        const updated = requirements.find(r => r.id === id)
        if (updated) setSelectedReq({ ...updated, status: 'approved' })
      }
    } catch (e: any) { setError(e.message) }
  }

  const handleAddCitation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedReq) return
    setSaving(true)
    try {
      await api.post(`/v1/requirements/${selectedReq.id}/citations`, {
        target_requirement_id: citationTarget,
        citation_type: citationType,
        citation_text: citationText,
      })
      setShowCitationModal(false)
      setCitationTarget('')
      setCitationText('')
      loadRequirements()
      // Reload selected
      const updated = await api.get(`/v1/requirements/${selectedReq.id}`)
      setSelectedReq(Array.isArray(updated) ? null : updated)
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  const handleVerifyCitation = async (citationId: string) => {
    if (!selectedReq) return
    try {
      await api.patch(`/v1/requirements/citations/${citationId}/verify`, {})
      loadRequirements()
    } catch (e: any) { setError(e.message) }
  }

  return (
    <div className="requirements-page">
      <div className="page-header">
        <h1>Requirements</h1>
        <p>EN 50128 requirements with bidirectional traceability</p>
      </div>

      <div className="flex justify-between items-center gap-12 mb-24">
        <div className="flex gap-8" style={{ flex: 1, maxWidth: 500 }}>
          <div className="search-bar" style={{ flex: 1 }}>
            <Search size={16} className="search-icon" />
            <input className="input search-input" placeholder="Search requirements…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ width: 140 }}>
            <option value="">All Status</option>
            {['draft', 'review', 'approved', 'verified', 'implemented', 'rejected'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={16} /> New Requirement
        </button>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Title</th><th>Priority</th><th>Status</th>
                <th>Safety Class</th><th>SIL</th><th>Verification</th><th>Traceability</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="text-muted text-sm">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={8} className="text-muted text-sm">No requirements found.</td></tr>
              ) : filtered.map(req => (
                <tr key={req.id} className="clickable-row" onClick={() => setSelectedReq(req)}>
                  <td><code style={{ fontSize: 12 }}>{req.requirement_id}</code></td>
                  <td><span style={{ maxWidth: 200, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{req.title}</span></td>
                  <td><span className={`badge ${req.priority === 'shall' ? 'badge-red' : req.priority === 'must' ? 'badge-amber' : 'badge-purple'}`}>{req.priority}</span></td>
                  <td><span className={`badge ${STATUS_COLORS[req.status] || 'badge-purple'}`}>{req.status}</span></td>
                  <td><span className="badge badge-purple">{req.safety_class}</span></td>
                  <td><span className={`badge ${req.sil_level === 'sil3' || req.sil_level === 'sil4' ? 'badge-red' : req.sil_level === 'sil2' ? 'badge-amber' : 'badge-green'}`}>{req.sil_level.toUpperCase()}</span></td>
                  <td><span className={`badge ${VERIF_COLORS[req.verification_status] || 'badge-purple'}`}>{req.verification_status}</span></td>
                  <td><span className="text-muted text-sm">{(req.citations ?? []).length} link(s)</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedReq && (
        <div className="modal-overlay" onClick={() => setSelectedReq(null)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{selectedReq.title}</h3>
                <code style={{ fontSize: 11, color: 'var(--text-muted)' }}>{selectedReq.requirement_id}</code>
              </div>
              <button className="btn btn-ghost" onClick={() => setSelectedReq(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div><label>Status</label><span className={`badge ${STATUS_COLORS[selectedReq.status]}`}>{selectedReq.status}</span></div>
                <div><label>Priority</label><span>{selectedReq.priority}</span></div>
                <div><label>Safety Class</label><span>{selectedReq.safety_class}</span></div>
                <div><label>SIL Level</label><span>{selectedReq.sil_level.toUpperCase()}</span></div>
                <div><label>Category</label><span>{selectedReq.category || '—'}</span></div>
                <div><label>Verification</label><span className={`badge ${VERIF_COLORS[selectedReq.verification_status]}`}>{selectedReq.verification_status} ({selectedReq.verification_method})</span></div>
                <div><label>Created</label><span>{new Date(selectedReq.created_at).toLocaleString()}</span></div>
                {selectedReq.approved_at && <div><label>Approved</label><span>{new Date(selectedReq.approved_at).toLocaleString()}</span></div>}
              </div>
              <div style={{ marginTop: 16 }}>
                <label>Description</label>
                <p className="text-sm" style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{selectedReq.description}</p>
              </div>

              <div style={{ marginTop: 20 }}>
                <div className="flex justify-between items-center mb-12">
                  <h4>Traceability Citations</h4>
                  <button className="btn btn-ghost btn-sm" onClick={() => setShowCitationModal(true)}>+ Add Citation</button>
                </div>
                {!selectedReq.citations || selectedReq.citations.length === 0 ? (
                  <p className="text-muted text-sm">No traceability links. Add citations to establish bidirectional links.</p>
                ) : (
                  <div className="citation-list">
                    {selectedReq.citations.map(c => (
                      <div key={c.id} className="citation-item">
                        <div className="flex items-center gap-8">
                          <span className="badge badge-purple">{c.citation_type}</span>
                          <code style={{ fontSize: 11 }}>{c.target_requirement_id}</code>
                          {c.verified
                            ? <CheckCircle size={14} style={{ color: 'var(--green)' }} />
                            : <button className="btn btn-ghost btn-sm" onClick={() => handleVerifyCitation(c.id)}>Verify</button>
                          }
                        </div>
                        {c.citation_text && <p className="text-sm text-muted" style={{ marginTop: 4 }}>{c.citation_text}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div className="modal-footer">
              {selectedReq.status === 'draft' || selectedReq.status === 'review' ? (
                <button className="btn btn-primary" onClick={() => handleApprove(selectedReq.id)}>
                  <CheckCircle size={14} /> Approve Requirement
                </button>
              ) : null}
              <button className="btn btn-ghost" onClick={() => setSelectedReq(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {showCitationModal && selectedReq && (
        <div className="modal-overlay" onClick={() => setShowCitationModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>Add Traceability Citation</h3><button className="btn btn-ghost" onClick={() => setShowCitationModal(false)}>✕</button></div>
            <form onSubmit={handleAddCitation}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Citation Type *</label>
                  <select className="input" value={citationType} onChange={e => setCitationType(e.target.value)}>
                    {CITATION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="form-group" style={{ marginTop: 12 }}>
                  <label>Target Requirement UUID *</label>
                  <input className="input" placeholder="UUID of target requirement" value={citationTarget} onChange={e => setCitationTarget(e.target.value)} required />
                </div>
                <div className="form-group" style={{ marginTop: 12 }}>
                  <label>Citation Text</label>
                  <textarea className="input" rows={3} placeholder="How does this citation relate?" value={citationText} onChange={e => setCitationText(e.target.value)} />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCitationModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Adding…' : 'Add Citation'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>New Requirement</h3><button className="btn btn-ghost" onClick={() => setShowModal(false)}>✕</button></div>
            <form onSubmit={handleCreate}>
              <div className="modal-body">
                {error && <div className="alert-error mb-16">{error}</div>}
                <div className="form-grid">
                  <div className="form-group"><label>Requirement ID *</label><input className="input" placeholder="e.g., REQ-SIG-001" value={form.requirement_id} onChange={e => setForm({ ...form, requirement_id: e.target.value })} required /></div>
                  <div className="form-group"><label>Title *</label><input className="input" placeholder="Brief title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required /></div>
                  <div className="form-group">
                    <label>Priority</label>
                    <select className="input" value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })}>
                      {['shall', 'must', 'should', 'may'].map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Category</label>
                    <select className="input" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                      {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Safety Class</label>
                    <select className="input" value={form.safety_class} onChange={e => setForm({ ...form, safety_class: e.target.value })}>
                      {SAFETY_CLASSES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>SIL Level</label>
                    <select className="input" value={form.sil_level} onChange={e => setForm({ ...form, sil_level: e.target.value })}>
                      {SIL_LEVELS.map(s => <option key={s} value={s}>{s.toUpperCase()}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Verification Method</label>
                    <select className="input" value={form.verification_method} onChange={e => setForm({ ...form, verification_method: e.target.value })}>
                      {['inspection', 'analysis', 'test', 'demonstration'].map(v => <option key={v} value={v}>{v}</option>)}
                    </select>
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label>Description *</label>
                    <textarea className="input" rows={4} placeholder="Full requirement text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} required />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Creating…' : 'Create Requirement'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
